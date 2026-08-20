from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

embeddings=HuggingFaceEmbeddings(model="sentence-transformers/all-MiniLM-L6-v2")

def create_embeddings(chunks):
     database=Chroma.from_texts(
          texts=chunks,
          embedding=embeddings,
          persist_directory="chroma-db"
     )
     return database

def load_embeddings():
     return Chroma(
          persist_directory="chroma-db",
          embedding_function=embeddings
     )

