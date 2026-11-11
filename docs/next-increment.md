# Roadmap after M2

## Done in M2 (local AI)

- **Local models via Ollama:** `embeddinggemma` for embeddings, `qwen3.5:9b` for answers.
  Provider-agnostic interfaces in `apps/api/app/ai/` (`EmbeddingProvider`, `ChatProvider`),
  selected per job by `EMBEDDING_PROVIDER` / `CHAT_PROVIDER`.
- **Background semantic indexing** with backoff when Ollama is down and automatic re-embedding
  when the embedding model changes.
- **Hybrid search:** full-text and HNSW cosine candidates merged by reciprocal-rank fusion;
  each hit reports `match_reasons` (`keyword`, `semantic`).
- **Ask (`POST /api/ask`, streaming NDJSON):** Recall / Plan / Report / Brainstorm modes,
  `[n]` citations validated server-side, no model call when nothing relevant is retrieved,
  prompt-injection hardening (delimited passages, neutralised tags, no images/links in output).

## M2.5: quality and ergonomics (small, high value)

1. **Evaluation set:** 20–30 real questions with the passages that should answer them, stored
   in `apps/api/eval/`. A script reports retrieval recall@k and citation accuracy so model and
   threshold changes are measured, not guessed.
2. **Follow-up questions:** `chat_sessions` / `chat_messages` tables (cited chunk ids stored
   per message); the next question is rewritten into a standalone query before retrieval.
3. **Date filters:** parse "last month" / "this year" into a `created_at` range on retrieval.
4. **Hosted answering (optional):** `OpenAIChatProvider` behind `CHAT_PROVIDER=openai`;
   embeddings stay local, so only each question's passages leave the machine.

## M3: a model of you (enrichment + memories)

Background jobs after `embedding_status = done`, using the local chat model:

```sql
source_summaries(source_id, summary, model, created_at)
topics(id, name, slug)            source_topics(source_id, topic_id, weight)
memories(id, statement, category, status: pending|active|superseded|rejected,
         confidence, valid_from, valid_to, superseded_by, created_at, reviewed_at)
memory_evidence(memory_id, chunk_id)
```

- `MemoryExtractor.propose()` (`app/ai/memory.py`) only ever creates `pending` rows. Nothing
  becomes `active` without an explicit user action (approve / edit / reject / supersede).
- Memory page: pending inbox, active memories by category (skills, interests, goals,
  preferences), contradictions flagged when a new candidate conflicts with an active one.
- Active memories are added to Ask context (with provenance), which makes plans and advice
  personal.

## M4: insights and connections

- **Related notes** on every source (nearest neighbours by embedding, with a one-line
  explanation of the shared idea).
- **Trends:** topic counts over time (timeline chart), "rising" and "fading" topics.
- **Cross-domain connections:** pairs of sources from different topics with unusually high
  similarity, explained by the model ("Kalman filters ↔ baseball tracking").
- **Connections graph:** interactive force-directed view; nodes = topics, sources, memories;
  edges = similarity, shared topics, evidence. Click a node to open it.
