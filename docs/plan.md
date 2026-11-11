# BrainDump — Implementation Plan

## Iteration goal (M0–M1)

A locally running app where I can type a note or upload a PDF / Markdown / plain-text
file, watch it get ingested, browse my library, and keyword-search everything.
Architectural seams exist for embeddings, memory extraction, and grounded chat, but
none of those are faked: the UI and API report them as unavailable.

## Architecture

```
apps/web   React + TypeScript + Vite + Tailwind + TanStack Query
apps/api   FastAPI + Pydantic + SQLAlchemy 2 + Alembic (+ in-process ingestion worker)
infra/     nginx config for the containerised web app
Postgres 16 + pgvector (Docker Compose)
```

### Ingestion pipeline

1. **Capture** — `POST /api/sources/notes` (JSON) or `POST /api/sources/files` (multipart).
   - Files are streamed with a hard size cap, then validated by extension **and** content
     sniffing (`%PDF-` header for PDFs, strict UTF-8/UTF-16 decoding with no binary bytes
     for text/markdown).
   - SHA-256 content hash → dedup via a unique `(kind, content_hash)` constraint. Duplicates
     return `409` with the existing source id.
   - Originals are stored on disk under `DATA_DIR/uploads/<sha256>`; a `sources` row is
     created with status `pending`.
2. **Process** — a DB-backed worker thread claims jobs with `SELECT … FOR UPDATE SKIP LOCKED`
   and a processing lease (crash-safe, restart-safe, multi-process-safe).
   - Parse (pypdf per page / UTF-8 text), normalise, chunk (~1,000 chars, paragraph-aware,
     never crossing PDF pages), write chunks, build a weighted `tsvector`
     (title = A, body = B).
   - Status: `pending → processing → ready | failed` with a user-facing error message.
     Failed sources can be retried.
3. **Search** — Postgres full-text search (`websearch_to_tsquery`, `ts_rank_cd`,
   `ts_headline`), grouped by source, returning the best-matching chunk + highlighted
   snippet segments (no HTML injection).

### Seams (interfaces only, not wired to endpoints)

- `app/ai/embeddings.py` — `EmbeddingProvider` protocol and a config-driven factory
  (`EMBEDDING_PROVIDER=none` → keyword-only). `chunks.embedding vector(1536)` column exists.
- `app/ai/memory.py` — `MemoryExtractor` protocol + `MemoryCandidate`.
- `app/ai/answering.py` — `GroundedAnswerer` protocol + `Answer` / `Citation`.

### Privacy & safety

- Logs contain ids, sizes, statuses and error codes only — never content, filenames,
  or search queries (uvicorn access log is replaced with a query-string-free logger;
  nginx log format omits query strings).
- Secrets come from environment variables / `.env` (git-ignored).
- Uploaded content is treated as inert data: it is parsed and indexed, never executed,
  rendered as HTML, or passed to a model as instructions.

## Milestones

- [x] M0 — monorepo, Docker Compose, migrations, health endpoint, CI-able lint/test commands
- [x] M1 — capture (note + upload), validation, dedup, worker, library, search, detail view,
      status states, seed data, tests
- [ ] M2 — embeddings + hybrid retrieval (see `docs/next-increment.md`)
- [ ] M3 — cited Q&A over retrieved chunks
- [ ] M4 — user-reviewed memories
