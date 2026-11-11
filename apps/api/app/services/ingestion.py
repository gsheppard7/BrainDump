"""Source creation, job claiming, and processing. Logs ids and codes only — never content."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import PurePath

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError, IngestionError
from app.models import Chunk, EmbeddingStatus, FileType, Source, SourceKind, SourceStatus
from app.services.chunking import assemble
from app.services.parsing import Segment, parse_file
from app.services.storage import FileStorage
from app.services.text import derive_title, normalize_text
from app.services.validation import validate_upload

logger = logging.getLogger(__name__)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _find_duplicate(session: Session, kind: SourceKind, content_hash: str) -> Source | None:
    return session.scalar(
        select(Source).where(Source.kind == kind, Source.content_hash == content_hash)
    )


def _duplicate_error(existing: Source) -> AppError:
    return AppError(
        409,
        "duplicate",
        f"This is already in your library as “{existing.title}”.",
        {"existing_source_id": str(existing.id)},
    )


def _insert(session: Session, source: Source) -> Source:
    session.add(source)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _find_duplicate(session, source.kind, source.content_hash)
        if existing is None:
            raise
        raise _duplicate_error(existing) from None
    logger.info("source created id=%s kind=%s size=%d", source.id, source.kind, source.size_bytes)
    return source


def create_note(session: Session, settings: Settings, body: str, title: str | None) -> Source:
    normalized = normalize_text(body)
    if not normalized:
        raise AppError(422, "empty_note", "Write something before saving.")
    if len(normalized) > settings.max_note_chars:
        raise AppError(
            413,
            "note_too_long",
            f"Notes are limited to {settings.max_note_chars:,} characters. "
            "Upload longer text as a .txt or .md file.",
        )
    clean_title = normalize_text(title or "")[:300] or derive_title(normalized, "Untitled note")
    content_hash = sha256(normalized.encode())
    existing = _find_duplicate(session, SourceKind.note, content_hash)
    if existing:
        raise _duplicate_error(existing)
    return _insert(
        session,
        Source(
            kind=SourceKind.note,
            title=clean_title,
            note_body=normalized,
            size_bytes=len(normalized.encode()),
            content_hash=content_hash,
            status=SourceStatus.pending,
        ),
    )


def create_file_source(
    session: Session, settings: Settings, storage: FileStorage, filename: str | None, data: bytes
) -> Source:
    validated = validate_upload(filename, data, settings.max_upload_bytes)
    content_hash = sha256(data)
    existing = _find_duplicate(session, SourceKind.file, content_hash)
    if existing:
        raise _duplicate_error(existing)
    storage_path = storage.save(content_hash, data)
    return _insert(
        session,
        Source(
            kind=SourceKind.file,
            file_type=validated.file_type,
            title=PurePath(validated.filename).stem[:300] or validated.filename,
            original_filename=validated.filename,
            size_bytes=len(data),
            content_hash=content_hash,
            storage_path=storage_path,
            status=SourceStatus.pending,
        ),
    )


def delete_source(session: Session, storage: FileStorage, source: Source) -> None:
    storage_path = source.storage_path
    session.delete(source)
    session.commit()
    if storage_path:
        storage.delete(storage_path)
    logger.info("source deleted id=%s", source.id)


def retry_source(session: Session, source: Source) -> Source:
    if source.status is not SourceStatus.failed:
        raise AppError(409, "not_failed", "Only failed sources can be retried.")
    source.status = SourceStatus.pending
    source.attempts = 0
    source.error_code = None
    source.error_message = None
    session.commit()
    return source


def recover_interrupted(session: Session) -> int:
    """Re-queue jobs left in `processing` by a previous run. Assumes one API process."""
    result = session.execute(
        update(Source)
        .where(Source.status == SourceStatus.processing)
        .values(status=SourceStatus.pending, processing_started_at=None)
    )
    session.commit()
    return result.rowcount


def claim_next(session: Session, settings: Settings) -> uuid.UUID | None:
    """Atomically claim one pending (or lease-expired) source. Safe across processes."""
    now = datetime.now(UTC)
    lease_cutoff = now - timedelta(seconds=settings.worker_lease_seconds)
    with session.begin():
        source = session.scalar(
            select(Source)
            .where(
                or_(
                    Source.status == SourceStatus.pending,
                    (Source.status == SourceStatus.processing)
                    & (Source.processing_started_at < lease_cutoff),
                )
            )
            .order_by(Source.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if source is None:
            return None
        if source.attempts >= settings.worker_max_attempts:
            _mark_failed(
                source,
                "too_many_attempts",
                "Processing was interrupted repeatedly. Retry, or re-upload the file.",
            )
            return None
        source.status = SourceStatus.processing
        source.processing_started_at = now
        source.attempts += 1
        return source.id


def _mark_failed(source: Source, code: str, message: str) -> None:
    source.status = SourceStatus.failed
    source.error_code = code
    source.error_message = message
    source.processing_started_at = None
    logger.info("source failed id=%s code=%s", source.id, code)


def _load_segments(source: Source, settings: Settings, storage: FileStorage):
    if source.kind is SourceKind.note:
        return [Segment(source.note_body or "")], None, None
    if not source.storage_path or source.file_type is None:
        raise IngestionError("missing_file", "The original file is missing.")
    try:
        data = storage.read(source.storage_path)
    except FileNotFoundError as exc:
        raise IngestionError("missing_file", "The original file is missing.") from exc
    parsed = parse_file(data, FileType(source.file_type), settings.max_pdf_pages)
    return parsed.segments, parsed.page_count, parsed.title


def process_source(session: Session, settings: Settings, storage: FileStorage, source_id) -> None:
    source = session.get(Source, source_id)
    if source is None:
        return
    try:
        segments, page_count, parsed_title = _load_segments(source, settings, storage)
        full_text, spans = assemble(segments)
        if not spans:
            raise IngestionError("no_text", "No text was found to index.")

        session.execute(delete(Chunk).where(Chunk.source_id == source.id))
        session.add_all(
            Chunk(
                source_id=source.id,
                ordinal=i,
                text=full_text[span.start : span.end],
                char_start=span.start,
                char_end=span.end,
                page=span.page,
            )
            for i, span in enumerate(spans)
        )
        if source.kind is SourceKind.file:
            if parsed_title:
                source.title = parsed_title[:300]
            elif source.file_type is FileType.markdown:
                source.title = derive_title(full_text, source.title)
        session.flush()
        session.execute(
            text(
                "UPDATE chunks SET tsv = "
                "setweight(to_tsvector('english', :title), 'A') || "
                "setweight(to_tsvector('english', text), 'B') "
                "WHERE source_id = :sid"
            ),
            {"title": source.title, "sid": source.id},
        )
        source.text_content = full_text
        source.char_count = len(full_text)
        source.page_count = page_count
        source.status = SourceStatus.ready
        source.embedding_status = EmbeddingStatus.pending
        source.error_code = None
        source.error_message = None
        source.processing_started_at = None
        source.processed_at = datetime.now(UTC)
        session.commit()
        logger.info("source ready id=%s chunks=%d", source.id, len(spans))
    except IngestionError as exc:
        session.rollback()
        source = session.get(Source, source_id)
        if source is not None:
            _mark_failed(source, exc.code, exc.message)
            session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("source processing crashed id=%s error=%s", source_id, type(exc).__name__)
        source = session.get(Source, source_id)
        if source is not None:
            _mark_failed(
                source, "internal_error", "Something went wrong while processing. Try again."
            )
            session.commit()
