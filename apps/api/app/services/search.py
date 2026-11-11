"""Keyword search over chunks using Postgres full-text search."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

# Control characters are stripped from all indexed text, so they can't collide with content.
HL_START = "\x02"
HL_END = "\x03"

_SEARCH_SQL = text(
    f"""
WITH q AS (SELECT websearch_to_tsquery('english', :query) AS query),
hits AS (
    SELECT c.id AS chunk_id, c.source_id,
           ts_rank_cd(c.tsv, q.query) AS rank,
           row_number() OVER (
               PARTITION BY c.source_id ORDER BY ts_rank_cd(c.tsv, q.query) DESC, c.ordinal
           ) AS rn,
           count(*) OVER (PARTITION BY c.source_id) AS match_count
    FROM chunks c
    JOIN sources s ON s.id = c.source_id AND s.status = 'ready'
    CROSS JOIN q
    WHERE c.tsv @@ q.query
),
total AS (SELECT count(DISTINCT source_id) AS n FROM hits)
SELECT s.id AS source_id, s.title, s.kind, s.file_type, s.created_at,
       c.id AS chunk_id, c.ordinal, c.page,
       h.rank, h.match_count, total.n AS total,
       ts_headline('english', c.text, q.query,
           'StartSel={HL_START}, StopSel={HL_END}, MaxWords=40, MinWords=15, '
           'MaxFragments=2, FragmentDelimiter=" … "') AS headline
FROM hits h
JOIN chunks c ON c.id = h.chunk_id
JOIN sources s ON s.id = h.source_id
CROSS JOIN q CROSS JOIN total
WHERE h.rn = 1
ORDER BY h.rank DESC, s.created_at DESC
LIMIT :limit OFFSET :offset
"""
)

_QUERY_IS_EMPTY_SQL = text("SELECT numnode(websearch_to_tsquery('english', :query)) = 0")


@dataclass(frozen=True)
class SnippetPart:
    text: str
    highlight: bool


@dataclass(frozen=True)
class SearchHit:
    source_id: uuid.UUID
    title: str
    kind: str
    file_type: str | None
    created_at: datetime
    chunk_id: uuid.UUID
    chunk_ordinal: int
    page: int | None
    rank: float
    match_count: int
    snippet: list[SnippetPart]


@dataclass(frozen=True)
class SearchResult:
    hits: list[SearchHit]
    total: int
    query_has_terms: bool


def parse_headline(headline: str) -> list[SnippetPart]:
    parts: list[SnippetPart] = []
    rest = headline
    while rest:
        start = rest.find(HL_START)
        if start == -1:
            parts.append(SnippetPart(rest, False))
            break
        if start:
            parts.append(SnippetPart(rest[:start], False))
        end = rest.find(HL_END, start)
        if end == -1:
            parts.append(SnippetPart(rest[start + 1 :], True))
            break
        parts.append(SnippetPart(rest[start + 1 : end], True))
        rest = rest[end + 1 :]
    return [p for p in parts if p.text]


def search(session: Session, query: str, limit: int = 20, offset: int = 0) -> SearchResult:
    if session.scalar(_QUERY_IS_EMPTY_SQL, {"query": query}):
        return SearchResult(hits=[], total=0, query_has_terms=False)
    rows = session.execute(_SEARCH_SQL, {"query": query, "limit": limit, "offset": offset}).all()
    hits = [
        SearchHit(
            source_id=r.source_id,
            title=r.title,
            kind=r.kind,
            file_type=r.file_type,
            created_at=r.created_at,
            chunk_id=r.chunk_id,
            chunk_ordinal=r.ordinal,
            page=r.page,
            rank=float(r.rank),
            match_count=int(r.match_count),
            snippet=parse_headline(r.headline),
        )
        for r in rows
    ]
    total = int(rows[0].total) if rows else 0
    return SearchResult(hits=hits, total=total, query_has_terms=True)
