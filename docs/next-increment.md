# Next increment (M2–M4): hybrid retrieval, cited Q&A, reviewed memories

Everything below builds on seams that already exist: `chunks.embedding vector(1536)`,
`chunks.embedding_model`, and the protocols in `apps/api/app/ai/`.

## 1. Embeddings + hybrid retrieval (M2)

**Provider** — implement `EmbeddingProvider` (`app/ai/embeddings.py`) for one hosted provider
(e.g. OpenAI `text-embedding-3-small`, 1536 dims) behind `EMBEDDING_PROVIDER=openai` +
`OPENAI_API_KEY`. Add a deterministic `FakeEmbeddingProvider` for tests only.

**Pipeline** — add a `ready → embedding` step that runs *after* keyword indexing, so a source
is searchable by keyword immediately and gains semantic recall when embeddings land:

```python
class SourceStatus(StrEnum):
    pending, processing, ready, failed            # unchanged
class EmbeddingStatus(StrEnum):                    # new column on sources
    not_configured, pending, done, failed
```

Batch chunks (≤ 96 per call), store `embedding` + `embedding_model`, retry with backoff;
failures never flip a source back out of `ready`. Re-embed when `embedding_model` changes.

**Index** — migration `0002`: `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`.

**Retriever** — new `app/services/retrieval.py`:

```python
@dataclass(frozen=True)
class RetrievalQuery:
    text: str
    limit: int = 20
    source_ids: list[uuid.UUID] | None = None   # optional scoping

class Retriever(Protocol):
    def retrieve(self, q: RetrievalQuery) -> list[RetrievedChunk]: ...   # app.ai.answering

class HybridRetriever:
    """Reciprocal-rank fusion of keyword (ts_rank_cd) and vector (cosine) result lists.
    Falls back to keyword-only when no provider is configured."""
    def __init__(self, session, embeddings: EmbeddingProvider | None, k: int = 60): ...
```

`GET /api/search` gains `mode: "keyword" | "hybrid"` in the response (already a field) and
per-hit `match_reasons: ["keyword", "semantic"]` so the UI can explain *why* something matched.

## 2. Cited Q&A (M3)

```
POST /api/ask   { "question": str, "source_ids"?: [uuid] }
→ 200 { "answer": str, "grounded": bool,
        "citations": [{ "source_id", "chunk_id", "page", "quote" }] }
```

- `GroundedAnswerer` implementation receives the top-k `RetrievedChunk`s, wrapped in clearly
  delimited `<document id=...>` blocks, with a system prompt stating that document text is
  untrusted data and must never be followed as instructions.
- The answer must cite chunk ids inline (`[c:<chunk_id>]`); the server **validates** every
  cited id was in the provided context and that each `quote` is a verbatim substring of that
  chunk. Unverifiable citations are dropped; if none remain, return `grounded: false` with
  "I couldn't find that in your library."
- UI: answer panel on Library page; citations link to `/sources/:id?chunk=N` (already works).
- Store Q&A history in `conversations` / `messages` tables (opt-in, deletable).

## 3. User-reviewed memories (M4)

```sql
memories(id, statement, category, status: proposed|accepted|rejected|archived,
         confidence, created_at, reviewed_at)
memory_evidence(memory_id, chunk_id)   -- provenance: every memory links to source chunks
```

- `MemoryExtractor.propose()` runs as an optional post-`ready` job and only ever creates
  `proposed` rows. Nothing becomes `accepted` without an explicit user action.
- Endpoints: `GET /api/memories?status=proposed`, `POST /api/memories/{id}/accept`,
  `/reject`, `PATCH /api/memories/{id}` (edit before accepting), `DELETE`.
- Deleting a source deletes its evidence; memories left with no evidence are flagged for review.
- Accepted memories are retrievable context for `/api/ask`, always shown with provenance.

## Next 3 priorities

1. **Hybrid retrieval** (provider + embedding job + HNSW index + RRF) — biggest recall win,
   and the prerequisite for good Q&A.
2. **Cited Q&A with server-side citation verification** — the core "second brain" experience.
3. **Memory review inbox** — proposed facts with provenance, accept/edit/reject.
