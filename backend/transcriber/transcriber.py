import whisper
import os
# from audioprocessor.audioprocessing import process_audio

MODEL_NAME=os.getenv("TRANSCRIPTION_MODEL",default="tiny")

_model=None

def load_model():
     global _model

     if _model==None:
          _model=whisper.load_model(MODEL_NAME)

     return _model

def transcribe_chunk(path:str , translate:bool=False):
     model=load_model()
     task="translate" if translate else "transcribe"
     text=model.transcribe(path,task="translate")
     return text["text"]

def transcribe(chunks:list , translate:bool=False):
     transcript=""
     for i , chunk in enumerate(chunks):
          text=transcribe_chunk(chunk,translate)
          transcript+=text + " "
     return text

