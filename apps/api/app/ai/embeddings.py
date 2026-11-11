from typing import Protocol

from app.config import Settings


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def get_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """None means embeddings are disabled and search is keyword-only."""
    if settings.embedding_provider == "none":
        return None
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
