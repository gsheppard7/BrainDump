"""Library search: hybrid retrieval grouped by source, with highlighted snippets."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.retrieval import Candidate, MatchReason, has_keyword_terms, retrieve

# Control characters are stripped from all indexed text, so they can't collide with content.
HL_START = "\x02"
HL_END = "\x03"

_DETAILS_SQL = text(
    f"""
    SELECT s.id AS source_id, s.title, s.kind, s.file_type, s.created_at,
           c.id AS chunk_id, c.ordinal, c.page,
           ts_headline('english', c.text, websearch_to_tsquery('english', :query),
               'StartSel={HL_START}, StopSel={HL_END}, MaxWords=40, MinWords=15, '
               'MaxFragments=2, FragmentDelimiter=" … "') AS headline
    FROM chunks c JOIN sources s ON s.id = c.source_id
    WHERE c.id = ANY(:ids)
    """
)


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
    match_reasons: list[MatchReason]
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


@dataclass
class _SourceGroup:
    best: Candidate
    score: float
    match_count: int
    reasons: set[MatchReason]


def _group_by_source(candidates: list[Candidate]) -> list[_SourceGroup]:
    groups: dict[uuid.UUID, _SourceGroup] = {}
    for cand in candidates:  # already sorted best-first
        group = groups.get(cand.source_id)
        if group is None:
            groups[cand.source_id] = _SourceGroup(cand, cand.score, 1, set(cand.reasons))
        else:
            group.match_count += 1
            group.reasons.update(cand.reasons)
    return sorted(groups.values(), key=lambda g: g.score, reverse=True)


def search(
    session: Session,
    query: str,
    *,
    limit: int = 20,
    offset: int = 0,
    query_vector: list[float] | None = None,
    min_similarity: float = 0.25,
    candidates: int = 100,
) -> SearchResult:
    has_terms = has_keyword_terms(session, query)
    if not has_terms and query_vector is None:
        return SearchResult(hits=[], total=0, query_has_terms=False)

    fused = retrieve(
        session,
        query,
        query_vector,
        match="all",
        candidates=candidates,
        min_similarity=min_similarity,
    )
    groups = _group_by_source(fused)
    page = groups[offset : offset + limit]
    if not page:
        return SearchResult(hits=[], total=len(groups), query_has_terms=True)

    rows = session.execute(
        _DETAILS_SQL, {"query": query, "ids": [g.best.chunk_id for g in page]}
    ).all()
    by_chunk = {r.chunk_id: r for r in rows}
    hits = []
    for group in page:
        r = by_chunk.get(group.best.chunk_id)
        if r is None:
            continue
        hits.append(
            SearchHit(
                source_id=r.source_id,
                title=r.title,
                kind=r.kind,
                file_type=r.file_type,
                created_at=r.created_at,
                chunk_id=r.chunk_id,
                chunk_ordinal=r.ordinal,
                page=r.page,
                rank=group.score,
                match_count=group.match_count,
                match_reasons=sorted(group.reasons),
                snippet=parse_headline(r.headline),
            )
        )
    return SearchResult(hits=hits, total=len(groups), query_has_terms=True)
