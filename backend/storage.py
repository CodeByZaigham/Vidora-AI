#Per-video storage & metadata registry.

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import DATA_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VideoStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._load_existing()

    # bootstrap
    def _load_existing(self) -> None:
        if not DATA_DIR.exists():
            return
        for folder in DATA_DIR.iterdir():
            meta_path = folder / "meta.json"
            if folder.is_dir() and meta_path.exists():
                try:
                    with open(meta_path, encoding="utf-8") as f:
                        self._cache[folder.name] = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue

    # CRUD
    def create(
        self,
        source_type: str,
        source: str,
        translate_to_english: bool = False,
        chunk_minutes: Optional[int] = None,
    ) -> str:
        """Register a new video and return its id. Does NOT start processing."""
        video_id = uuid.uuid4().hex[:12]
        self.dir(video_id).mkdir(parents=True, exist_ok=True)

        meta = {
            "video_id": video_id,
            "source_type": source_type,      # "youtube" | "upload"
            "source": source,                 # original url or filename
            "source_title": None,             # filename / yt-dlp title, known early
            "translate_to_english": translate_to_english,
            "chunk_minutes": chunk_minutes,   # None means "use the server default"
            "status": "queued",               # queued -> processing -> ready | failed
            "progress": "Queued",
            "error": None,
            "title": None,
            "summary": None,
            "questions": None,
            "decisions": None,
            "actions": None,
            "transcript_path": None,
            "chroma_dir": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        with self._lock:
            self._cache[video_id] = meta
        self._persist(video_id)
        return video_id

    def update(self, video_id: str, **fields: Any) -> None:
        with self._lock:
            meta = self._cache.get(video_id)
            if meta is None:
                return
            meta.update(fields)
            meta["updated_at"] = _now()
        self._persist(video_id)

    def get(self, video_id: str) -> Optional[dict[str, Any]]:
        return self._cache.get(video_id)

    def all(self) -> list[dict[str, Any]]:
        return sorted(self._cache.values(), key=lambda m: m["created_at"], reverse=True)

    def delete(self, video_id: str) -> None:
        with self._lock:
            self._cache.pop(video_id, None)


    # filesystem helpers
    def dir(self, video_id: str) -> Path:
        return DATA_DIR / video_id

    def _persist(self, video_id: str) -> None:
        meta = self._cache.get(video_id)
        if meta is None:
            return
        with open(self.dir(video_id) / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)


store = VideoStore()
