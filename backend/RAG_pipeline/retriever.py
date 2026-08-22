from langchain_community.vectorstores import Chroma
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from llm import get_llm


def retrieve_embeddings(query:str , db:Chroma):
     retriever=db.as_retriever(
          search_type="similarity",
          search_kwargs={"k":8}
     )

     query_variations=MultiQueryRetriever.from_llm(
          llm=get_llm(),
          retriever=retriever
     )

     result=query_variations.invoke(query)

     return result
