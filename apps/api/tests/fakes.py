import hashlib
import math
import re
from collections.abc import Iterator

from app.ai.chat import ChatMessage
from app.models import EMBEDDING_DIMENSIONS

# Words that the fake embedder treats as meaning the same thing.
CONCEPTS = {
    "automobile": "car",
    "vehicle": "car",
    "mechanic": "car",
    "loaf": "bread",
    "sourdough": "bread",
    "baking": "bread",
}


def _concept(word: str) -> str:
    return CONCEPTS.get(word, word)


class FakeEmbeddingProvider:
    """Deterministic bag-of-concepts vectors, so synonyms land near each other."""

    dimensions = EMBEDDING_DIMENSIONS

    def __init__(self, model: str = "fake-embed", fail: bool = False) -> None:
        self.model = model
        self.fail = fail
        self.calls = 0

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for word in re.findall(r"[a-z]+", text.lower()):
            if len(word) < 4:
                continue
            idx = int(hashlib.md5(_concept(word).encode()).hexdigest(), 16) % self.dimensions
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str], title: str | None = None) -> list[list[float]]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("embedding backend down")
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        if self.fail:
            raise RuntimeError("embedding backend down")
        return self._vector(text)


class FakeChatProvider:
    location = "local"

    def __init__(self, chunks: list[str], error: Exception | None = None) -> None:
        self.model = "fake-chat"
        self.chunks = chunks
        self.error = error
        self.messages: list[ChatMessage] | None = None

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        self.messages = messages
        yield from self.chunks
        if self.error:
            raise self.error
