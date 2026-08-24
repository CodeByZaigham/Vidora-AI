from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/")
def root():
    return {"message": "AI Video Assistant API is running", "docs": "/docs"}


@router.get("/health")
def health():
    return {"status": "ok"}
