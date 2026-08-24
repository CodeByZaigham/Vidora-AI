import os
import threading

import whisper

MODEL_NAME = os.getenv("TRANSCRIPTION_MODEL", "tiny")

_model = None
_model_lock = threading.Lock()


def load_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # re-check inside the lock
                _model = whisper.load_model(MODEL_NAME)
    return _model


def transcribe_chunk(path: str, translate: bool = False) -> str:
    model = load_model()
    task = "translate" if translate else "transcribe"
    result = model.transcribe(path, task=task)
    return result["text"].strip()


def transcribe(chunks: list[str], translate: bool = False) -> str:
    """Transcribe each chunk in order and join them into one full transcript."""
    parts = []
    for i, chunk_path in enumerate(chunks):
        text = transcribe_chunk(chunk_path, translate)
        parts.append(text)
    return " ".join(parts).strip()
