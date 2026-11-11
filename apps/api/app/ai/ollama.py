"""Minimal client for a local Ollama server (https://github.com/ollama/ollama/blob/main/docs/api.md)."""

import json
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Ollama returned an error for this request."""


class OllamaUnavailable(OllamaError):
    """Ollama isn't reachable or the model isn't installed; retrying later may succeed."""


class OllamaClient:
    def __init__(
        self, base_url: str, timeout: float, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout, connect=3.0),
            transport=transport,
        )

    def _raise_for(self, response: httpx.Response, model: str | None) -> None:
        if response.is_success:
            return
        try:
            detail = str(response.json().get("error", ""))
        except ValueError:
            detail = ""
        if response.status_code == 404 and model:
            raise OllamaUnavailable(
                f"The model '{model}' isn't installed. Run: ollama pull {model}"
            )
        raise OllamaError(f"Ollama error {response.status_code}: {detail[:200]}")

    def list_models(self, timeout: float = 2.0) -> list[str]:
        try:
            response = self._http.get("/api/tags", timeout=timeout)
        except httpx.HTTPError as exc:
            raise OllamaUnavailable("Ollama isn't running.") from exc
        self._raise_for(response, None)
        return [m["name"] for m in response.json().get("models", [])]

    def embed(self, model: str, inputs: list[str]) -> list[list[float]]:
        try:
            response = self._http.post(
                "/api/embed", json={"model": model, "input": inputs, "truncate": True}
            )
        except httpx.HTTPError as exc:
            raise OllamaUnavailable("Ollama isn't running.") from exc
        self._raise_for(response, model)
        embeddings = response.json().get("embeddings") or []
        if len(embeddings) != len(inputs):
            raise OllamaError("Ollama returned the wrong number of embeddings.")
        return embeddings

    def chat_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        options: dict[str, Any],
        think: bool | None,
    ) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options,
        }
        if think is not None:
            payload["think"] = think
        try:
            with self._http.stream("POST", "/api/chat", json=payload) as response:
                if not response.is_success:
                    response.read()
                    self._raise_for(response, model)
                for line in response.iter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise OllamaError(str(event["error"])[:200])
                    content = event.get("message", {}).get("content")
                    if content:
                        yield content
                    if event.get("done"):
                        return
        except httpx.HTTPError as exc:
            raise OllamaUnavailable("Lost connection to Ollama.") from exc


@lru_cache
def get_client(base_url: str, timeout: float) -> OllamaClient:
    return OllamaClient(base_url, timeout)
