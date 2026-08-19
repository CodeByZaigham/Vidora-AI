import yt_dlp
from pydub import AudioSegment
import os

FOLDER="downloads"
os.makedirs(FOLDER,exist_ok=True)

def download_youtube_audio(url:str) -> str:
     output=os.path.join(FOLDER,"%(title)s.%(ext)s")
     ydl_opt={
          "format":"bestaudio/best",
          "outtmpl":output,
        #   "ffmpeg_location": r"C:\Users\hp\Downloads\ffmpeg-9.0.1-full_build\bin", #give your own path 
          "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
     }
     with yt_dlp.YoutubeDL(ydl_opt) as ydl:
          info = ydl.extract_info(url, download=True)
          filename = ydl.prepare_filename(info).replace(".webm", ".wav").replace(".m4a", ".wav")

     return filename

def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format="wav")
    return output_path

download_youtube_audio("https://www.youtube.com/watch?v=EDb37y_MhRw&pp=ygUDaWJt")