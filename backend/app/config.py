"""Kaagaz — settings, read from backend/.env. Secrets stay server-side."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Kaagaz"
    # Pipeline: PyMuPDF text layer + scanned-page images -> vision LLM -> schema-validated JSON
    llm_base_url: str = "https://openrouter.ai/api/v1"   # any OpenAI-compatible API (Ollama: http://localhost:11434/v1)
    openrouter_api_key: str = ""
    llm_model: str = "google/gemini-2.5-flash"           # must accept images + json_schema output
    llm_reasoning: str = "low"                           # reasoning effort; "" for non-reasoning models
    llm_timeout_s: int = 180
    max_image_pages: int = 10                            # scanned pages sent per document (cost cap)
    # Uploads
    max_upload_mb: int = 15
    max_files: int = 20
    # Storage / security
    database_url: str = ""
    secret_key: str = ""            # signs session cookies
    file_encryption_key: str = ""   # Fernet key; encrypts stored PDFs
    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False     # True in production (HTTPS)
    session_hours: int = 12
    retention_days: int = 90        # stored PDFs are purged after this; reports are kept
    worker_enabled: bool = True     # run the job worker inside the API process


settings = Settings()
