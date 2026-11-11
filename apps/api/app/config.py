from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://braindump:braindump@localhost:5433/braindump"
    data_dir: Path = Path("./data")
    max_upload_mb: int = 20
    max_note_chars: int = 200_000
    max_pdf_pages: int = 2_000
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    worker_enabled: bool = True
    worker_poll_seconds: float = 1.0
    worker_lease_seconds: int = 600
    worker_max_attempts: int = 3

    embedding_provider: Literal["none", "ollama"] = "none"
    chat_provider: Literal["none", "ollama"] = "none"
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 180.0
    embedding_model: str = "embeddinggemma"
    embedding_batch_size: int = 32
    chat_model: str = "qwen3.5:9b"
    chat_num_ctx: int = 8192
    chat_temperature: float = 0.3
    chat_think: bool | None = False

    # Cosine similarity below which a vector match is treated as unrelated. Calibrated for
    # embeddinggemma: unrelated questions score < 0.15, related ones > 0.33.
    vector_min_similarity: float = 0.25
    retrieval_candidates: int = 100
    ask_context_chars: int = 14_000

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
