from typing import Protocol

from app.ai.ollama import OllamaClient, OllamaError

# (query template, document template). Ollama's /api/embed applies no prompt template, and
# these models were trained to expect task prefixes.
PROMPT_TEMPLATES: dict[str, tuple[str, str]] = {
    "embeddinggemma": ("task: search result | query: {text}", "title: {title} | text: {text}"),
    "nomic-embed-text": ("search_query: {text}", "search_document: {text}"),
}


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    def embed_documents(self, texts: list[str], title: str | None = None) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OllamaEmbeddingProvider:
    def __init__(self, client: OllamaClient, model: str, dimensions: int) -> None:
        self._client = client
        self.model = model
        self.dimensions = dimensions
        family = model.split(":", 1)[0]
        self._query_tpl, self._doc_tpl = PROMPT_TEMPLATES.get(family, ("{text}", "{text}"))

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        vectors = self._client.embed(self.model, inputs)
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise OllamaError(
                    f"'{self.model}' produces {len(vector)}-dimension vectors but the database "
                    f"expects {self.dimensions}. Use a {self.dimensions}-dimension model or add "
                    "a migration."
                )
        return vectors

    def embed_documents(self, texts: list[str], title: str | None = None) -> list[list[float]]:
        safe_title = (title or "none").replace("|", " ")
        return self._embed([self._doc_tpl.format(title=safe_title, text=t) for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self._query_tpl.format(text=text)])[0]
