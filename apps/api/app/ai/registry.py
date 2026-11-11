"""Builds AI providers from settings. Tests swap in fakes with `override()`."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from app.ai.chat import ChatProvider, OllamaChatProvider
from app.ai.embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from app.ai.ollama import OllamaError, get_client
from app.config import Settings
from app.models import EMBEDDING_DIMENSIONS

_UNSET = object()
_overrides: dict[str, object] = {}


def get_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """None means embeddings are disabled and search is keyword-only."""
    if "embedding" in _overrides:
        return _overrides["embedding"]  # type: ignore[return-value]
    if settings.embedding_provider == "ollama":
        client = get_client(settings.ollama_base_url, settings.ollama_timeout_seconds)
        return OllamaEmbeddingProvider(client, settings.embedding_model, EMBEDDING_DIMENSIONS)
    return None


def get_chat_provider(settings: Settings) -> ChatProvider | None:
    if "chat" in _overrides:
        return _overrides["chat"]  # type: ignore[return-value]
    if settings.chat_provider == "ollama":
        client = get_client(settings.ollama_base_url, settings.ollama_timeout_seconds)
        return OllamaChatProvider(
            client,
            settings.chat_model,
            num_ctx=settings.chat_num_ctx,
            temperature=settings.chat_temperature,
            think=settings.chat_think,
        )
    return None


@contextmanager
def override(embedding: object = _UNSET, chat: object = _UNSET) -> Iterator[None]:
    previous = dict(_overrides)
    if embedding is not _UNSET:
        _overrides["embedding"] = embedding
    if chat is not _UNSET:
        _overrides["chat"] = chat
    try:
        yield
    finally:
        _overrides.clear()
        _overrides.update(previous)


@dataclass
class AIStatus:
    provider: str
    location: str
    embedding_model: str | None
    chat_model: str | None
    reachable: bool
    missing_models: list[str] = field(default_factory=list)
    message: str | None = None

    @property
    def embeddings_ready(self) -> bool:
        return (
            self.embedding_model is not None
            and self.reachable
            and (self.embedding_model not in self.missing_models)
        )

    @property
    def chat_ready(self) -> bool:
        return (
            self.chat_model is not None
            and self.reachable
            and (self.chat_model not in self.missing_models)
        )


def _installed(model: str, installed: list[str]) -> bool:
    names = set(installed) | {name.removesuffix(":latest") for name in installed}
    return model in names


def ai_status(settings: Settings) -> AIStatus:
    embedding = get_embedding_provider(settings)
    chat = get_chat_provider(settings)
    status = AIStatus(
        provider="ollama" if (embedding or chat) else "none",
        location="local",
        embedding_model=embedding.model if embedding else None,
        chat_model=chat.model if chat else None,
        reachable=False,
    )
    if status.provider == "none":
        return status
    if _overrides:
        status.provider = "test"
        status.reachable = True
        return status
    try:
        installed = get_client(
            settings.ollama_base_url, settings.ollama_timeout_seconds
        ).list_models()
    except OllamaError as exc:
        status.message = f"{exc} Start it with: brew services start ollama"
        return status
    status.reachable = True
    status.missing_models = [
        m for m in (status.embedding_model, status.chat_model) if m and not _installed(m, installed)
    ]
    if status.missing_models:
        status.message = "Missing models. Run: " + " && ".join(
            f"ollama pull {m}" for m in status.missing_models
        )
    return status
