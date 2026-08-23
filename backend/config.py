from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
load_dotenv()
import os

class Settings(BaseSettings):
    # --- LLM ---
    mistral_api_key: str = os.getenv("MISTRAL_API_KEY")
    llm_model: str = "mistral-medium-latest"

    # --- Transcription ---
    transcription_model: str = "tiny"          # whisper model size: tiny/base/small/medium/large
    chunk_minutes: int = 10                     # length of each audio chunk fed to whisper

    
    yt_dlp_max_retries: int = 3
    yt_dlp_retry_backoff_seconds: float = 5.0    # doubles each retry (5s, 10s, 20s, ...)
    # Optional path to a Netscape-format cookies.txt (exported from a logged-in
    # browser session). Authenticated requests are blocked/rate-limited far
    # less often than anonymous ones.
    yt_cookies_file: str = ""

    # --- Storage ---
    data_dir: str = "data"                      # root folder where every video's artifacts live
    keep_audio_files: bool = False               # keep downloaded/converted audio after transcription

    # --- API ---
    cors_origins: str = "*"                      # comma separated list, or "*"
    max_upload_mb: int = 1024                    # reject uploads bigger than this

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
DATA_DIR = Path(settings.data_dir).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
