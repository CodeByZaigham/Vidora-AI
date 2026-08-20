from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_text(text: str):
     split=RecursiveCharacterTextSplitter(
          chunk_size=1000,
          chunk_overlap=50
     )

     return split.split_text(text)