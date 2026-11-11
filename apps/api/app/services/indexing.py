"""Background semantic indexing: embed chunks of ready sources. Keyword search never waits on it."""

import logging
from datetime import UTC, datetime

from sqlalchemy import exists, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.ai.embeddings import EmbeddingProvider
from app.models import Chunk, EmbeddingStatus, Source, SourceStatus

logger = logging.getLogger(__name__)


class EmbeddingFailed(RuntimeError):
    pass


def requeue_stale(session: Session, model: str) -> int:
    """Queue ready sources that were never embedded or were embedded with a different model."""
    stale_chunk = exists().where(
        Chunk.source_id == Source.id,
        or_(Chunk.embedding_model.is_(None), Chunk.embedding_model != model),
    )
    result = session.execute(
        update(Source)
        .where(
            Source.status == SourceStatus.ready,
            or_(
                Source.embedding_status.is_(None),
                (Source.embedding_status == EmbeddingStatus.done) & stale_chunk,
            ),
        )
        .values(embedding_status=EmbeddingStatus.pending)
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return result.rowcount


def embed_next(
    session_factory: sessionmaker[Session], provider: EmbeddingProvider, batch_size: int
) -> bool:
    """Embed one pending source. Returns False when the queue is empty."""
    source_id = None
    try:
        with session_factory() as session, session.begin():
            source = session.scalar(
                select(Source)
                .where(
                    Source.status == SourceStatus.ready,
                    Source.embedding_status == EmbeddingStatus.pending,
                )
                .order_by(Source.embedding_attempted_at.asc().nulls_first(), Source.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if source is None:
                return False
            source_id = source.id
            chunks = session.scalars(
                select(Chunk).where(Chunk.source_id == source.id).order_by(Chunk.ordinal)
            ).all()
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start : start + batch_size]
                vectors = provider.embed_documents([c.text for c in batch], title=source.title)
                for chunk, vector in zip(batch, vectors, strict=True):
                    chunk.embedding = vector
                    chunk.embedding_model = provider.model
            source.embedding_status = EmbeddingStatus.done
            source.embedding_attempted_at = datetime.now(UTC)
        logger.info("source embedded id=%s chunks=%d", source_id, len(chunks))
        return True
    except Exception as exc:
        if source_id is not None:
            with session_factory() as session:
                session.execute(
                    update(Source)
                    .where(Source.id == source_id)
                    .values(embedding_attempted_at=datetime.now(UTC))
                )
                session.commit()
        raise EmbeddingFailed(type(exc).__name__) from exc
