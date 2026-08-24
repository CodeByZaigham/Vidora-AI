from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

_embeddings: HuggingFaceEmbeddings | None = None


def get_embedding_function() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _embeddings


def create_embeddings(chunks: list[str], persist_directory: str, collection_name: str) -> Chroma:
    return Chroma.from_texts(
        texts=chunks,
        embedding=get_embedding_function(),
        persist_directory=persist_directory,
        collection_name=collection_name,
    )


def load_embeddings(persist_directory: str, collection_name: str) -> Chroma:
    return Chroma(
        persist_directory=persist_directory,
        embedding_function=get_embedding_function(),
        collection_name=collection_name,
    )


def release_chroma_client(persist_directory: str) -> None:
    """Force-release chromadb's cached client/connection for one specific
    persist_directory.
    """
    try:
        from chromadb.api.client import SharedSystemClient
        system = SharedSystemClient._identifier_to_system.pop(persist_directory, None)
        SharedSystemClient._identifier_to_refcount.pop(persist_directory, None)
        if system is not None:
            system.stop()
    except Exception:
        # Best-effort: if chromadb's internals differ in some installed
        # version, the retry loop in the delete route is the fallback.
        pass
    finally:
        import gc
        gc.collect()

