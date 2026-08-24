from langchain_chroma import Chroma
from langchain_classic.retrievers.multi_query import MultiQueryRetriever

from llm import get_llm


def retrieve_embeddings(query: str, db: Chroma, k: int = 8) -> list:
    retriever = db.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )

    query_variations = MultiQueryRetriever.from_llm(
        llm=get_llm(),
        retriever=retriever,
    )

    return query_variations.invoke(query)
