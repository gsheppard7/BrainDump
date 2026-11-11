# BrainDump

A personal second brain. Capture notes and documents, then find them again.

- **Capture:** write a note or upload a PDF / Markdown / plain-text file and watch it process.
- **Library:** **hybrid search** — exact words *and* related meaning — with highlighted
  snippets that link straight to the matching passage.
- **Ask:** questions, plans, reports, or brainstorms answered from your own notes, with
  numbered citations back to the exact passages, and "I couldn't find that" when your notes
  don't cover it. Every answer is saved in History so you can reopen it later.
- **Brain:** an interactive map of your sources, linked by shared meaning — the knowledge
  base as a growing graph.

All AI runs **locally via [Ollama](https://ollama.com)** — free, and your notes never leave
your Mac. Without Ollama, everything still works except Ask, and search falls back to
keyword-only (the UI says so).

> **Not yet built:** memory extraction/review, topics, trends, and the connections graph.
> See [`docs/next-increment.md`](docs/next-increment.md).

## Local AI setup (once)

```bash
brew install ollama
brew services start ollama                 # runs in the background, starts at login
ollama pull embeddinggemma                 # 0.6 GB — meaning-based search
ollama pull qwen3.5:9b                     # 7.6 GB — answers on the Ask page
```

Ollama runs natively (not in Docker) so it can use the Apple GPU. The model needs ~8 GB of
free memory while answering and unloads itself after a few idle minutes. On a 24 GB M4 Pro a
typical answer starts in 5–10 s and finishes in ~15 s.

## Quick start (Docker — everything else)

Requires Docker.

```bash
cp .env.example .env
docker compose up --build -d          # Postgres+pgvector, API, web
docker compose exec api python -m app.seed   # optional: sample notes, Markdown, text, PDF
open http://localhost:8080
```

Stop with `docker compose down` (data is kept). `docker compose down -v` deletes the database
volume; uploaded originals live in `apps/api/data/`.

## Local development (hot reload)

Requires Docker (for Postgres), [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
cp .env.example .env
docker compose up -d db                               # Postgres on localhost:5433

cd apps/api
uv sync
uv run alembic upgrade head
uv run python -m app.seed                             # optional
uv run uvicorn app.main:app --reload --port 8000      # API on :8000

cd apps/web                                           # in another terminal
npm install
npm run dev                                           # http://localhost:5173 (proxies /api)
```

The Docker `api` service and the local API share the same database and `apps/api/data/`
directory, so run one or the other at a time (both use port 8000). A `Makefile` wraps
these commands (`make db`, `make api`, `make web`, `make check`).

## Checks

```bash
docker compose up -d db               # API tests use a separate braindump_test database
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd apps/web && npm run lint && npm run typecheck && npm test && npm run build
```

## Acceptance walkthrough

Files for this live in [`samples/`](samples/).

1. **Add a note** — Capture → write a note → *Save note* (or ⌘/Ctrl+Enter). It appears in
   *Recent captures* as Queued → Processing → Ready.
2. **Upload a PDF** — drop `samples/reading-notes-systems-thinking.pdf` on the upload area.
   Watch the progress bar, then the status badge.
3. **Search** — Library → type `leverage points`. The snippet highlights matches and shows
   the page number.
4. **Open the source** — click the result. The matching passage is outlined and scrolled
   into view; query terms are highlighted.
5. **Restart** — `docker compose down && docker compose up -d`. Everything is still there.
   Jobs interrupted mid-processing are automatically re-queued on startup.
6. **Errors** — try `samples/quarterly-report.docx` (unsupported type),
   `samples/not-really-a.pdf` (content doesn't match extension),
   `samples/scanned-receipt-no-text.pdf` (accepted, then fails with an OCR explanation and a
   *Retry* button), the same PDF twice (duplicate, links to the existing copy), or a file
   over 20 MB: `python3 -c "open('/tmp/big.txt','w').write('a'*21_000_000)"`.
   `samples/prompt-injection-test.md` shows that document text is only ever indexed, never
   acted on.
7. **Search by meaning** — search for a concept using different words than your notes use
   (e.g. "money worries" for a note about budgets). Each result is tagged *words*,
   *meaning*, or both.
8. **Ask** — with the sample data loaded: Ask → *Recall* → "What order should I restart the
   home network in?" The answer
   streams in with numbered citations; click one to jump to the passage. Ask something your
   notes don't cover ("What's the capital of France?") and it says it couldn't find it.

## How it works

| Piece | Choice |
| --- | --- |
| Web | React 19, TypeScript, Vite, Tailwind 4, TanStack Query, React Router |
| API | FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, pypdf |
| Data | Postgres 16 + pgvector; originals on disk, content-addressed by SHA-256 |
| Jobs | Postgres-backed queue (`FOR UPDATE SKIP LOCKED` + lease) run by a worker thread in the API |
| Search | Postgres full-text + pgvector (HNSW, cosine) merged with reciprocal-rank fusion |
| AI | Ollama: `embeddinggemma` (768-dim embeddings), `qwen3.5:9b` (answers), both local |

- **Semantic indexing:** after a source is keyword-indexed (instantly searchable), the worker
  embeds its chunks in the background. If Ollama is down it backs off and retries; nothing
  fails. Changing `EMBEDDING_MODEL` re-embeds everything on next start.
- **Ask:** the question is embedded, the best 8–14 passages are retrieved (hybrid, max 4 per
  source, ~14k characters), and the local model answers with `[n]` citations. The server
  reports which citation numbers are valid; the UI only links those. If retrieval finds
  nothing relevant, the model isn't called at all.

- **Validation:** extension allow-list *and* content sniffing (PDF header; strict UTF-8 /
  BOM-marked UTF-16 for text). Size is capped while streaming and via `Content-Length`
  before the body is read. Filenames are sanitised.
- **Dedup:** SHA-256 of file bytes (or normalised note text), enforced by a unique constraint.
  Duplicates return `409` with the existing source's id.
- **Chunking:** ~1,000-character paragraph-aware chunks with exact character offsets; chunks
  never cross PDF pages, so results can cite a page.
- **Errors:** every API error is `{"error": {"code", "message", "details"}}` with a message
  safe to show to the user.

API docs: http://localhost:8000/docs.

### Privacy & safety

- Logs record ids, sizes, statuses and error codes — **never** note/document content,
  filenames, or search queries. Uvicorn's access log (which includes query strings) is
  replaced; nginx's log format omits query strings.
- Secrets come from the environment / `.env`, which is git-ignored. No secrets are required yet.
- Uploaded content is inert data: it's parsed and indexed, never executed or rendered as
  HTML. When passages are given to the model they're delimited, any passage tags inside
  them are neutralised, and the model is told they are untrusted data, never instructions.
  Answers render Markdown without images or external links (so a malicious document can't
  make the answer load a URL).
- With the default Ollama setup, no content leaves your machine.
- Single-user and local: there is **no authentication**. Don't expose the ports publicly.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://braindump:braindump@localhost:5433/braindump` | |
| `DATA_DIR` | `./data` | Uploaded originals (`apps/api/data` when run from `apps/api`) |
| `MAX_UPLOAD_MB` | `20` | nginx allows 25 MB so the API can return its own message |
| `EMBEDDING_PROVIDER` | `ollama` | `none` = keyword-only search |
| `CHAT_PROVIDER` | `ollama` | `none` disables Ask |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Docker uses `host.docker.internal` |
| `EMBEDDING_MODEL` | `embeddinggemma` | Must produce 768-dim vectors (or add a migration) |
| `CHAT_MODEL` | `qwen3.5:9b` | Any Ollama chat model; smaller = faster, weaker |
| `CHAT_NUM_CTX` | `8192` | Context window sent to Ollama (its default is too small for RAG) |
| `VECTOR_MIN_SIMILARITY` | `0.25` | Below this, a meaning match counts as unrelated |
| `LOG_LEVEL` | `INFO` | |

## Known limitations

- No OCR: image-only PDFs fail with an explanation.
- Local-model answers are good for recall and summaries but weaker than hosted models on
  long reports and multi-step reasoning; always check the citations.
- Ask is single-turn (no follow-up questions yet) and has no date filters ("last month").
- Keyword search is English-stemmed with no typo tolerance.
- Files are read into memory (capped at `MAX_UPLOAD_MB`) for hashing and validation.
- The worker runs inside the API process; startup re-queues interrupted jobs, which assumes a
  single API process (the lease still prevents double-processing across processes).
- No auth, no multi-user support, no editing of notes after capture.

## Layout

```
apps/api     FastAPI service, migrations, tests, seed data
apps/web     React app
infra/       nginx config + web Dockerfile
samples/     files for manually exercising the acceptance test
docs/        plan.md (this iteration), next-increment.md (M2–M4 design)
```
