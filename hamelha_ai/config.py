import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_id: int = int(os.getenv("ADMIN_ID", "0") or 0)
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///data/hamelha.db")
    work_dir: str = os.getenv("WORK_DIR", "data/work")
    free_credits: int = int(os.getenv("FREE_CREDITS", "5"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    ffmpeg: str = os.getenv("FFMPEG", "ffmpeg")

settings = Settings()
