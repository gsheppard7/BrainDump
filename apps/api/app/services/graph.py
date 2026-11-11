"""Knowledge-base graph: sources as nodes, meaning-similarity as edges.

Each ready, semantically-indexed source becomes a node whose position in meaning-space is
the average of its chunk embeddings. Edges connect sources whose centroids are similar
enough that they likely share themes — the "brain map" of how notes relate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chunk, EmbeddingStatus, Source, SourceStatus


@dataclass(frozen=True)
class GraphNode:
    id: str
    title: str
    kind: str
    file_type: str | None
    char_count: int
    chunk_count: int
    created_at: datetime
    embedding_status: str | None


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    weight: float


@dataclass(frozen=True)
class KnowledgeGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    pending_sources: int
    min_similarity: float


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _average_embeddings(session: Session) -> dict[str, list[float]]:
    """Mean embedding per source that has at least one embedded chunk."""
    rows = session.execute(
        select(Chunk.source_id, Chunk.embedding).where(Chunk.embedding.is_not(None))
    ).all()
    sums: dict[str, list[float]] = {}
    counts: dict[str, int] = {}
    for source_id, vector in rows:
        if not vector:
            continue
        key = str(source_id)
        if key not in sums:
            sums[key] = [float(v) for v in vector]
            counts[key] = 1
        else:
            for i, value in enumerate(vector):
                sums[key][i] += float(value)
            counts[key] += 1
    return {key: [v / counts[key] for v in total] for key, total in sums.items()}


def build_graph(
    session: Session,
    *,
    min_similarity: float = 0.4,
    max_edges: int = 500,
) -> KnowledgeGraph:
    sources = session.scalars(
        select(Source)
        .where(Source.status == SourceStatus.ready)
        .order_by(Source.created_at.asc())
    ).all()
    pending = sum(1 for s in sources if s.embedding_status == EmbeddingStatus.pending)
    centroids = _average_embeddings(session)

    chunk_counts = {
        str(source_id): count
        for source_id, count in session.execute(
            select(Chunk.source_id, func.count()).group_by(Chunk.source_id)
        ).all()
    }

    nodes = [
        GraphNode(
            id=str(s.id),
            title=s.title,
            kind=s.kind.value,
            file_type=s.file_type.value if s.file_type else None,
            char_count=s.char_count or 0,
            chunk_count=chunk_counts.get(str(s.id), 0),
            created_at=s.created_at,
            embedding_status=s.embedding_status.value if s.embedding_status else None,
        )
        for s in sources
    ]

    # All pairwise similarities among indexed sources, keep those above the threshold.
    indexed_ids = [n.id for n in nodes if n.id in centroids]
    scored: list[tuple[float, str, str]] = []
    for i, left in enumerate(indexed_ids):
        for right in indexed_ids[i + 1 :]:
            sim = _cosine(centroids[left], centroids[right])
            if sim >= min_similarity:
                scored.append((sim, left, right))
    scored.sort(reverse=True)
    edges = [
        GraphEdge(source=a, target=b, weight=round(sim, 4))
        for sim, a, b in scored[:max_edges]
    ]
    return KnowledgeGraph(
        nodes=nodes, edges=edges, pending_sources=pending, min_similarity=min_similarity
    )


def graph_as_dict(graph: KnowledgeGraph) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": n.id,
                "title": n.title,
                "kind": n.kind,
                "file_type": n.file_type,
                "char_count": n.char_count,
                "chunk_count": n.chunk_count,
                "created_at": n.created_at.isoformat(),
                "embedding_status": n.embedding_status,
            }
            for n in graph.nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target, "weight": e.weight} for e in graph.edges
        ],
        "stats": {
            "sources": len(graph.nodes),
            "connections": len(graph.edges),
            "indexed": sum(1 for n in graph.nodes if n.embedding_status == "done"),
            "pending": graph.pending_sources,
            "min_similarity": graph.min_similarity,
        },
    }
