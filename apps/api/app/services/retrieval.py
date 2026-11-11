"""Hybrid chunk retrieval: full-text + pgvector cosine, merged by reciprocal-rank fusion."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

RRF_K = 60

_KEYWORD_QUERIES = {
    # Library search: every term must match (websearch syntax: "phrases", -exclusions, or).
    "all": "websearch_to_tsquery('english', :query)",
    # Ask: natural-language questions match on any meaningful term.
    "any": "replace(plainto_tsquery('english', :query)::text, '&', '|')::tsquery",
}

MatchReason = Literal["keyword", "semantic"]


@dataclass
class Candidate:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    score: float = 0.0
    reasons: list[MatchReason] = field(default_factory=list)
    similarity: float | None = None


@dataclass(frozen=True)
class Passage:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    ordinal: int
    page: int | None
    text: str
    title: str
    kind: str
    file_type: str | None
    created_at: datetime
    reasons: list[MatchReason]


def tsquery_sql(match: Literal["all", "any"]) -> str:
    return _KEYWORD_QUERIES[match]


def has_keyword_terms(session: Session, query: str, match: Literal["all", "any"] = "all") -> bool:
    return bool(session.scalar(text(f"SELECT numnode({tsquery_sql(match)}) > 0"), {"query": query}))


def keyword_candidates(
    session: Session, query: str, limit: int, match: Literal["all", "any"] = "all"
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    if not has_keyword_terms(session, query, match):
        return []
    rows = session.execute(
        text(
            f"""
            WITH q AS (SELECT {tsquery_sql(match)} AS query)
            SELECT c.id, c.source_id
            FROM chunks c
            JOIN sources s ON s.id = c.source_id AND s.status = 'ready'
            CROSS JOIN q
            WHERE c.tsv @@ q.query
            ORDER BY ts_rank_cd(c.tsv, q.query) DESC, c.ordinal
            LIMIT :limit
            """
        ),
        {"query": query, "limit": limit},
    ).all()
    return [(r.id, r.source_id) for r in rows]


def to_vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


def vector_candidates(
    session: Session, vector: list[float], limit: int, min_similarity: float
) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
    session.execute(text(f"SET LOCAL hnsw.ef_search = {max(40, int(limit))}"))
    rows = session.execute(
        text(
            """
            SELECT c.id, c.source_id, 1 - (c.embedding <=> CAST(:vec AS vector)) AS similarity
            FROM chunks c
            JOIN sources s ON s.id = c.source_id AND s.status = 'ready'
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:vec AS vector)
            LIMIT :limit
            """
        ),
        {"vec": to_vector_literal(vector), "limit": limit},
    ).all()
    return [
        (r.id, r.source_id, float(r.similarity)) for r in rows if r.similarity >= min_similarity
    ]


def fuse(
    keyword: list[tuple[uuid.UUID, uuid.UUID]],
    semantic: list[tuple[uuid.UUID, uuid.UUID, float]],
) -> list[Candidate]:
    by_chunk: dict[uuid.UUID, Candidate] = {}
    for rank, (chunk_id, source_id) in enumerate(keyword):
        cand = by_chunk.setdefault(chunk_id, Candidate(chunk_id, source_id))
        cand.score += 1 / (RRF_K + rank + 1)
        cand.reasons.append("keyword")
    for rank, (chunk_id, source_id, similarity) in enumerate(semantic):
        cand = by_chunk.setdefault(chunk_id, Candidate(chunk_id, source_id))
        cand.score += 1 / (RRF_K + rank + 1)
        cand.reasons.append("semantic")
        cand.similarity = similarity
    return sorted(by_chunk.values(), key=lambda c: c.score, reverse=True)


def retrieve(
    session: Session,
    query: str,
    query_vector: list[float] | None,
    *,
    match: Literal["all", "any"],
    candidates: int,
    min_similarity: float,
) -> list[Candidate]:
    keyword = keyword_candidates(session, query, candidates, match)
    semantic = (
        vector_candidates(session, query_vector, candidates, min_similarity) if query_vector else []
    )
    return fuse(keyword, semantic)


def load_passages(session: Session, candidates: list[Candidate]) -> list[Passage]:
    if not candidates:
        return []
    rows = session.execute(
        text(
            """
            SELECT c.id, c.source_id, c.ordinal, c.page, c.text,
                   s.title, s.kind, s.file_type, s.created_at
            FROM chunks c JOIN sources s ON s.id = c.source_id
            WHERE c.id = ANY(:ids)
            """
        ),
        {"ids": [c.chunk_id for c in candidates]},
    ).all()
    by_id = {r.id: r for r in rows}
    passages = []
    for cand in candidates:
        r = by_id.get(cand.chunk_id)
        if r is None:
            continue
        passages.append(
            Passage(
                chunk_id=r.id,
                source_id=r.source_id,
                ordinal=r.ordinal,
                page=r.page,
                text=r.text,
                title=r.title,
                kind=r.kind,
                file_type=r.file_type,
                created_at=r.created_at,
                reasons=cand.reasons,
            )
        )
    return passages
