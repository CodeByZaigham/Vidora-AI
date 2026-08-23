import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI color codes (yt-dlp and ffmpeg both print colored output,
    which is unreadable once it lands in JSON/a UI)."""
    return _ANSI_RE.sub("", text)


def clean_error(exc: Exception, max_len: int = 600) -> str:
    """Turn an exception into a short, storable, human-readable string.
    Some libraries (ffmpeg in particular) raise exceptions whose message is
    an entire multi-hundred-line build config dump. We keep the full
    traceback in the server logs (via logger.exception) but only store a
    trimmed, plain-text summary in meta.json / API responses.
    """
    text = strip_ansi(str(exc)).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "... (truncated - see server logs for full detail)"
    return text
