import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routes import chat, insights, system, transcript, videos

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="AI Video Assistant",
    description=(
        "Turn any YouTube URL or locally uploaded video/audio file into a "
        "transcript, an AI-generated title/summary/questions/decisions/action "
        "items, and a question-answering assistant grounded in that video."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(videos.router)
app.include_router(transcript.router)
app.include_router(insights.router)
app.include_router(chat.router)
