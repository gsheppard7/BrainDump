from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol

from app.ai.ollama import OllamaClient


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


class ChatProvider(Protocol):
    model: str
    location: Literal["local", "hosted"]

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]: ...


class OllamaChatProvider:
    location: Literal["local", "hosted"] = "local"

    def __init__(
        self,
        client: OllamaClient,
        model: str,
        num_ctx: int,
        temperature: float,
        think: bool | None,
    ) -> None:
        self._client = client
        self.model = model
        self._options = {"num_ctx": num_ctx, "temperature": temperature}
        self._think = think

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        return self._client.chat_stream(
            self.model,
            [{"role": m.role, "content": m.content} for m in messages],
            self._options,
            self._think,
        )
