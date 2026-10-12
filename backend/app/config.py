"""ClaimLens AI — central settings (server-side keys, no secrets in frontend)."""
import os
from pydantic_settings import BaseSettings


def _default_host() -> str:
    # OLLAMA_HOST=0.0.0.0 means "listen on all interfaces" for the server,
    # but it is NOT a valid connect address for the client.
    h = os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip()
    if h.startswith("0.0.0.0"):
        h = h.replace("0.0.0.0", "127.0.0.1")
    if "://" not in h:
        h = "http://" + h
    return h


class Settings(BaseSettings):
    app_name: str = "ClaimLens AI"
    ollama_host: str = _default_host()
    ollama_model: str = "llama3.2:3b"  # local text LLM (fast, low RAM)
    ollama_vlm_model: str = ""  # e.g. moondream / llava — auto-detected if blank
    ollama_timeout_s: int = 120
    max_upload_mb: int = 15
    sqlite_path: str = "./data/claimlens.db"

    class Config:
        env_file = ".env"
        env_prefix = ""


settings = Settings()
