import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    PROJECT_NAME: str = "Claude AI Clone Backend"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./claude_clone.db")
    
    # Security & Session Session Cookies
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "session_id")
    SESSION_EXPIRY_DAYS: int = int(os.getenv("SESSION_EXPIRY_DAYS", "30"))
    
    # LLM Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # CORS Origins (Frontends)
    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]

settings = Settings()
