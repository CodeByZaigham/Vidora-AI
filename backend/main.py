from audioprocessor.audioprocessing import process_audio
from transcriber.transcriber import transcribe
from info_extractor.summarizer import summarize_chunks
from info_extractor import extractor as e
from RAG_pipeline.embeddings import create_embeddings,load_embeddings
from RAG_pipeline.retriever import retrieve_embeddings
from RAG_pipeline.ask_llm import ask

url="https://www.youtube.com/watch?v=qYNweeDHiyU&pp=ygUDaWJt"

chunks=process_audio(url)
transcript=transcribe(chunks)
summary=summarize_chunks(transcript)

print("\n===== TITLE =====\n") 
print(e.get_title(summary)) 
print("\n=================\n") 
print("\n===== SUMMARY =====\n") 
print(e.get_summary(summary))
print("\n===================\n") 
print("\n===== QUESTIONS =====\n") 
print(e.get_questions(summary)) 
print("\n=====================\n") 
print("\n===== DECISIONS =====\n") 
print(e.get_decisions(summary)) 
print("\n=====================\n")
print("\n===== ACTION ITEMS =====\n") 
print(e.get_actions(summary))
print("\n=======================\n")

# chunks=split_text(transcript)
db=load_embeddings()
query = input("ASK ANY QUESTION ABOUT THE VIDEO: ")
retrieved_chunks=retrieve_embeddings(query,db)
output=ask(query,retrieved_chunks)
print(output)