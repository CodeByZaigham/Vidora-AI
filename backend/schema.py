from typing import Optional

from pydantic import BaseModel, Field

# Requests

class VideoURLRequest(BaseModel):
    url: str = Field(..., description="YouTube (or any yt-dlp supported) video URL")
    translate_to_english: bool = Field(
        False, description="If true, Whisper translates non-English audio to English"
    )
    chunk_minutes: Optional[int] = Field(
        None, description="Override the default audio chunk length (minutes)"
    )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=20, description="Number of transcript chunks to retrieve")


class RetryRequest(BaseModel):
    """Optional overrides when retrying a failed video. Anything left as
    None reuses whatever was used on the original attempt."""
    translate_to_english: Optional[bool] = None
    chunk_minutes: Optional[int] = None



# Responses
class VideoStatus(BaseModel):
    video_id: str
    source_type: str
    source: str
    source_title: Optional[str] = None
    translate_to_english: bool = False
    chunk_minutes: Optional[int] = None
    status: str
    progress: str
    error: Optional[str] = None
    title: Optional[str] = None
    created_at: str
    updated_at: str


class VideoListResponse(BaseModel):
    videos: list[VideoStatus]


class TranscriptResponse(BaseModel):
    video_id: str
    transcript: str


class InsightsResponse(BaseModel):
    video_id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    questions: Optional[str] = None
    decisions: Optional[str] = None
    actions: Optional[str] = None


class AskResponse(BaseModel):
    video_id: str
    question: str
    answer: str
