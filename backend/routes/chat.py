from fastapi import APIRouter, HTTPException

from RAG_pipeline.ask_llm import ask
from RAG_pipeline.embeddings import load_embeddings
from RAG_pipeline.retriever import retrieve_embeddings
from schema import AskRequest, AskResponse
from storage import store

router = APIRouter(prefix="/videos", tags=["Chat / RAG"])


@router.post("/{video_id}/ask", response_model=AskResponse)
def ask_video(video_id: str, payload: AskRequest):
    meta = store.get(video_id)
    if not meta:
        raise HTTPException(404, "Video not found")
    if meta["status"] == "failed":
        raise HTTPException(422, f"Processing failed: {meta.get('error', 'unknown error')}")
    if meta["status"] != "ready" or not meta.get("chroma_dir"):
        raise HTTPException(409, f"Video is not ready to be queried yet (status: {meta['status']})")

    db = load_embeddings(persist_directory=meta["chroma_dir"], collection_name=video_id)
    retrieved_chunks = retrieve_embeddings(payload.question, db, k=payload.top_k)
    answer = ask(payload.question, retrieved_chunks)

    return {"video_id": video_id, "question": payload.question, "answer": answer}
