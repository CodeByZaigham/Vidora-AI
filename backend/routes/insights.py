from fastapi import APIRouter, HTTPException

from schema import InsightsResponse
from storage import store

router = APIRouter(prefix="/videos", tags=["Insights"])


@router.get("/{video_id}/insights", response_model=InsightsResponse)
def get_insights(video_id: str):
    meta = store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")
    if meta["status"] == "failed":
        raise HTTPException(422, f"Processing failed: {meta.get('error', 'unknown error')}")
    if meta["status"] != "ready":
        raise HTTPException(409, f"Insights not ready yet (status: {meta['status']})")

    return {
        "video_id": video_id,
        "title": meta.get("title"),
        "summary": meta.get("summary"),
        "questions": meta.get("questions"),
        "decisions": meta.get("decisions"),
        "actions": meta.get("actions"),
    }
