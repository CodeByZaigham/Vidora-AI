from llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import StrOutputParser

llm=get_llm()

def ask(query:str , retrieved_chunks:list)-> str:
     prompt = ChatPromptTemplate.from_messages([
     (
     "system",
     """You are an AI assistant that answers questions about a video.

     The user will ask questions about the video. You will receive relevant
     retrieved transcript excerpts from the video as context.

     Use the retrieved transcript excerpts as evidence to answer the user's
     question accurately.

     Important instructions:
     - Answer as if you are answering directly about the video.
     - NEVER say "from the retrieved context", "according to the context",
     "the provided context", "the transcript says", or similar phrases.
     - Do not mention RAG, retrieval, chunks, vector databases, embeddings,
     context windows, or the retrieval process.
     - Do not reveal that you were given retrieved chunks.
     - Do not make up information that is not supported by the provided
     video transcript context.
     - If the provided context does not contain enough information to answer
     the question, say: "I couldn't find enough information in the video
     to answer that question."
     - Give a clear, natural, and concise answer.
     - Answer the user's question directly rather than summarizing the context."""
     ),
     (
     "human",
     """Question:
     {question}

     Video information:
     {context}

     Answer the question directly."""
     )
     ])

     answer = RunnableSequence(prompt | llm | StrOutputParser())

     return answer.invoke({"question":query , "context":retrieved_chunks})