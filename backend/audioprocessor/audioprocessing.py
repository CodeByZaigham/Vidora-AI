import logging
import os
import time

import yt_dlp
from pydub import AudioSegment

from config import settings

logger = logging.getLogger("audioprocessing")

# Markers that indicate a transient/anti-bot failure worth retrying, as
# opposed to e.g. "video is private" or "video unavailable", which retrying
# will never fix.
_RETRYABLE_MARKERS = (
    "403",
    "forbidden",
    "429",
    "too many requests",
    "timed out",
    "timeout",
    "connection reset",
    "temporary failure",
    "http error 5",
    "unable to download webpage",
)


class DownloadError(RuntimeError):
    """Raised when a YouTube download fails after all retries are exhausted."""


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _RETRYABLE_MARKERS)


def _build_ydl_opts(outtmpl: str) -> dict:
    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "noplaylist": True,
        # yt-dlp's own low-level retries, on top of our higher-level ones
        "retries": 3,
        "fragment_retries": 3,
        "extractor_retries": 2,
        # Trying more than one player client is currently the most effective
        # workaround for YouTube's shifting bot-detection / signature checks.
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
            )
        },
    }
    if settings.yt_cookies_file and os.path.exists(settings.yt_cookies_file):
        opts["cookiefile"] = settings.yt_cookies_file
    return opts


def download_youtube_audio(url: str, output_dir: str) -> tuple[str, str | None]:
    os.makedirs(output_dir, exist_ok=True)
    outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
    ydl_opts = _build_ydl_opts(outtmpl)

    max_retries = max(1, settings.yt_dlp_max_retries)
    backoff = settings.yt_dlp_retry_backoff_seconds
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                filename = os.path.splitext(filename)[0] + ".wav"
            title = info.get("title") if isinstance(info, dict) else None
            return filename, title

        except Exception as exc:  # yt_dlp.utils.DownloadError and friends
            last_exc = exc
            retryable = _is_retryable(exc)
            logger.warning(
                "yt-dlp download attempt %s/%s failed (%s): %s",
                attempt, max_retries, "retryable" if retryable else "not retryable", exc,
            )
            if not retryable or attempt == max_retries:
                break
            sleep_for = backoff * (2 ** (attempt - 1))
            time.sleep(sleep_for)

    raise DownloadError(
        f"Unable to download this video after {max_retries} attempt(s). "
        "YouTube blocked or rejected the request. This usually means: "
        "(1) yt-dlp is out of date -- run `pip install -U yt-dlp`, "
        "(2) YouTube is rate-limiting/blocking this server's IP -- wait and "
        "retry, or (3) the video needs an authenticated session -- set "
        "YT_COOKIES_FILE to a cookies.txt exported from a logged-in browser. "
        f"Last error: {last_exc}"
    ) from last_exc


def convert_to_wav(input_path: str, output_dir: str) -> str:
    """Convert any local audio/video file to a mono 16kHz WAV (what Whisper wants)."""
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_converted.wav")

    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format="wav")
    return output_path


def chunk_audio(path: str, output_dir: str, chunksize: int = 10, min_chunk_seconds: float = 2.0) -> list[str]:
    """Split a WAV file into `chunksize`-minute pieces for the transcriber."""

    os.makedirs(output_dir, exist_ok=True)
    audio = AudioSegment.from_wav(path)
    duration_ms = len(audio)

    if duration_ms == 0:
        raise ValueError(
            "The downloaded/converted audio has zero duration. The source may have "
            "no audio track, or audio extraction failed silently -- check that the "
            "video actually contains audio."
        )

    chunksize_ms = max(1, chunksize * 60 * 1000)
    min_chunk_ms = max(1, int(min_chunk_seconds * 1000))

    boundaries: list[tuple[int, int]] = []
    start = 0
    while start < duration_ms:
        end = min(start + chunksize_ms, duration_ms)
        boundaries.append((start, end))
        start = end

    # Merge a too-short trailing remainder into the previous chunk rather
    # than exporting it as its own (near-)empty chunk.
    if len(boundaries) > 1 and (boundaries[-1][1] - boundaries[-1][0]) < min_chunk_ms:
        last_end = boundaries.pop()[1]
        prev_start, _ = boundaries[-1]
        boundaries[-1] = (prev_start, last_end)

    base_name = os.path.splitext(os.path.basename(path))[0]
    chunks = []
    for i, (start, end) in enumerate(boundaries):
        chunk = audio[start:end]
        chunk_path = os.path.join(output_dir, f"{base_name}_chunk[{i}].wav")
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)

    return chunks


def process_audio(source: str, output_dir: str, chunksize: int = 10) -> tuple[list[str], str | None]:
    print("processing audio...")
    title = None

    if source.startswith("http://") or source.startswith("https://"):
        wav_path, title = download_youtube_audio(source, output_dir)
    else:
        wav_path = convert_to_wav(source, output_dir)
        title = os.path.splitext(os.path.basename(source))[0]

    print("creating chunks..")
    chunks = chunk_audio(wav_path, output_dir, chunksize)
    return chunks, title
