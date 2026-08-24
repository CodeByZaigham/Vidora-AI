import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from schema import TranscriptResponse
from storage import store

router = APIRouter(prefix="/videos", tags=["Transcript"])


def _get_ready_meta(video_id: str) -> dict:
    meta = store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")
    if meta["status"] == "failed":
        raise HTTPException(422, f"Processing failed: {meta.get('error', 'unknown error')}")
    if not meta.get("transcript_path"):
        raise HTTPException(409, f"Transcript not ready yet (status: {meta['status']})")
    return meta


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9 ._-]", "", name).strip() or "transcript"
    return f"{name}.txt"


@router.get("/{video_id}/transcript", response_model=TranscriptResponse)
def get_transcript(video_id: str):
    meta = _get_ready_meta(video_id)
    text = open(meta["transcript_path"], encoding="utf-8").read()
    return {"video_id": video_id, "transcript": text}


@router.get("/{video_id}/transcript/download")
def download_transcript(video_id: str):
    """Returns the transcript as a plain .txt file attachment."""
    meta = _get_ready_meta(video_id)
    label = meta.get("title") or meta.get("source_title") or video_id
    return FileResponse(
        path=meta["transcript_path"],
        media_type="text/plain",
        filename=_safe_filename(label),
    )
