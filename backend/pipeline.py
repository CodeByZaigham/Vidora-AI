"""
The end-to-end pipeline for a single video, run in a background thread so
the API can accept and process many videos concurrently.
"""

import logging
import shutil
from pathlib import Path

from audioprocessor.audioprocessing import process_audio
from config import settings
from info_extractor import extractor
from info_extractor.summarizer import summarize_chunks
from RAG_pipeline.embeddings import create_embeddings
from RAG_pipeline.textsplitter import split_text
from storage import store
from transcriber.transcriber import transcribe
from utils import clean_error

logger = logging.getLogger("pipeline")


def run_pipeline(
    video_id: str,
    source: str,
    translate: bool = False,
    chunk_minutes: int | None = None,
) -> None:
    video_dir = store.dir(video_id)
    audio_dir = video_dir / "audio"

    try:
        # 1. audio acquisition + chunking
        store.update(video_id, status="processing", progress="Downloading / preparing audio")
        chunks, detected_title = process_audio(
            source, str(audio_dir), chunk_minutes or settings.chunk_minutes
        )
        if detected_title:
            store.update(video_id, source_title=detected_title)

        # 2. transcription
        store.update(video_id, progress=f"Transcribing {len(chunks)} audio chunk(s) with Whisper")
        transcript = transcribe(chunks, translate=translate)

        if not transcript:
            raise ValueError("Transcription produced no text (audio may be silent or unsupported).")

        # 3. persist transcript.txt
        transcript_path = video_dir / "transcript.txt"
        transcript_path.write_text(transcript, encoding="utf-8")
        store.update(
            video_id,
            progress="Transcript ready, generating insights",
            transcript_path=str(transcript_path),
        )

        # 4. chunk-level summaries feed all the extractors below
        summary_chunks = summarize_chunks(transcript)

        # 5. structured insights
        store.update(video_id, progress="Extracting title, summary, questions, decisions, actions")
        title = extractor.get_title(summary_chunks).strip()
        summary = extractor.get_summary(summary_chunks).strip()
        questions = extractor.get_questions(summary_chunks).strip()
        decisions = extractor.get_decisions(summary_chunks).strip()
        actions = extractor.get_actions(summary_chunks).strip()

        store.update(
            video_id,
            title=title,
            summary=summary,
            questions=questions,
            decisions=decisions,
            actions=actions,
            progress="Building searchable index",
        )

        # 6. this video's own, isolated vector store
        rag_chunks = split_text(transcript)
        chroma_dir = video_dir / "chroma_db"
        create_embeddings(rag_chunks, persist_directory=str(chroma_dir), collection_name=video_id)

        store.update(video_id, status="ready", progress="Ready", chroma_dir=str(chroma_dir))
        logger.info("Video %s finished processing successfully", video_id)

    except Exception as exc:  # noqa: BLE001 - we want to catch and record everything
        logger.exception("Pipeline failed for video %s", video_id)
        store.update(video_id, status="failed", progress="Failed", error=clean_error(exc))

    finally:
        # Whether this run succeeded or failed, the raw/partial audio in
        # audio_dir is no longer needed and shouldn't linger on disk.
        if not settings.keep_audio_files:
            _cleanup(audio_dir)


def _cleanup(audio_dir: Path) -> None:
    shutil.rmtree(audio_dir, ignore_errors=True)

