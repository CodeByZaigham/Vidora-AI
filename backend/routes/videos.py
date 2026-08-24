import shutil
import time

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from config import settings
from pipeline import run_pipeline
from RAG_pipeline.embeddings import release_chroma_client
from schema import RetryRequest, VideoListResponse, VideoStatus, VideoURLRequest
from storage import store

router = APIRouter(prefix="/videos", tags=["Videos"])


@router.post("/url", response_model=VideoStatus, status_code=202)
def submit_video_url(payload: VideoURLRequest, background_tasks: BackgroundTasks):
    """Register a YouTube URL and start processing it in the background."""
    video_id = store.create(
        source_type="youtube",
        source=payload.url,
        translate_to_english=payload.translate_to_english,
        chunk_minutes=payload.chunk_minutes,
    )
    background_tasks.add_task(
        run_pipeline, video_id, payload.url, payload.translate_to_english, payload.chunk_minutes
    )
    return store.get(video_id)


@router.post("/upload", response_model=VideoStatus, status_code=202)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="A local video or audio file"),
    translate_to_english: bool = False,
):
    """Upload a local video/audio file and start processing it the same way
    a YouTube URL would be processed (same pipeline, same insights, same
    per-video Chroma DB)."""
    if not file.filename:
        raise HTTPException(400, "Uploaded file has no filename")

    video_id = store.create(
        source_type="upload",
        source=file.filename,
        translate_to_english=translate_to_english,
    )
    source_dir = store.dir(video_id) / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    dest_path = source_dir / file.filename

    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    with open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                shutil.rmtree(store.dir(video_id), ignore_errors=True)
                store.delete(video_id)
                raise HTTPException(413, f"File exceeds the {settings.max_upload_mb}MB upload limit")
            out.write(chunk)

    background_tasks.add_task(run_pipeline, video_id, str(dest_path), translate_to_english, None)
    return store.get(video_id)


@router.get("", response_model=VideoListResponse)
def list_videos():
    """List every video that has ever been submitted, most recent first."""
    return {"videos": store.all()}


@router.get("/{video_id}", response_model=VideoStatus)
def get_video(video_id: str):
    meta = store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")
    return meta


@router.post("/{video_id}/retry", response_model=VideoStatus, status_code=202)
def retry_video(video_id: str, payload: RetryRequest, background_tasks: BackgroundTasks):
    """Re-run a failed video's pipeline without losing its video_id"""
    meta = store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")
    if meta["status"] != "failed":
        raise HTTPException(409, f"Only failed videos can be retried (current status: {meta['status']})")

    if meta["source_type"] == "youtube":
        source = meta["source"]
    else:
        source_dir = store.dir(video_id) / "source"
        candidates = [p for p in source_dir.glob("*") if p.is_file()] if source_dir.exists() else []
        if not candidates:
            raise HTTPException(
                409, "The originally uploaded file is no longer available; please upload it again."
            )
        source = str(candidates[0])

    translate_to_english = (
        payload.translate_to_english
        if payload.translate_to_english is not None
        else meta.get("translate_to_english", False)
    )
    chunk_minutes = (
        payload.chunk_minutes if payload.chunk_minutes is not None else meta.get("chunk_minutes")
    )

    store.update(
        video_id,
        status="queued",
        progress="Retry queued",
        error=None,
        translate_to_english=translate_to_english,
        chunk_minutes=chunk_minutes,
    )
    background_tasks.add_task(run_pipeline, video_id, source, translate_to_english, chunk_minutes)
    return store.get(video_id)


@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: str):
    """Delete a video's folder entirely: source/audio files, transcript,
    insights, and its own Chroma DB. This does not touch any other video.
    """
    meta = store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")

    chroma_dir = meta.get("chroma_dir")
    if chroma_dir:
        release_chroma_client(chroma_dir)

    video_dir = store.dir(video_id)
    last_exc: OSError | None = None
    for attempt in range(5):
        try:
            if video_dir.exists():
                shutil.rmtree(video_dir)
            last_exc = None
            break
        except OSError as exc:
            last_exc = exc
            time.sleep(0.3 * (attempt + 1))

    if last_exc is not None:
        raise HTTPException(500, f"Could not fully delete video data: {last_exc}")

    store.delete(video_id)
    return None

