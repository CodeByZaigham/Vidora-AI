# Vidora-AI
Think Otter.ai, but for any video. FastAPI backend transcribes with Whisper, extracts summaries/decisions/action-items via LangChain + Mistral, and powers semantic RAG chat per video using ChromaDB embeddings. Async background pipeline, documented REST API, vanilla JS frontend.

# Development Plan (initial)

step 1: give video url or upload local video

step 2: break it into chunks for easy transcription using whisper

step 3: again split the transcription and summarize every chunk for info extraction like questions and decisions

step 4: create embeddings or that chunks for usage in RAG pipeline

step 5: setup RAG pipelines and retrieving strategies

step 6: chatbot creation for QnA. 