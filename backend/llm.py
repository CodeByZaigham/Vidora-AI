from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv
load_dotenv()

def get_llm():
     return ChatMistralAI(model="mistral-medium-latest")