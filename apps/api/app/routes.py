import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.ai.embeddings import get_embedding_provider
from app.config import Settings, get_settings
from app.db import get_session
from app.errors import AppError
from app.models import Source, SourceKind, SourceStatus
from app.schemas import (
    Capabilities,
    MetaResponse,
    NoteCreate,
    SearchResponse,
    SourceDetail,
    SourceList,
    SourceSummary,
)
from app.services import ingestion
from app.services.search import search
from app.services.storage import FileStorage
from app.services.validation import EXTENSIONS, file_too_large

router = APIRouter(prefix="/api")

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
READ_CHUNK = 1024 * 1024


def get_storage(settings: SettingsDep) -> FileStorage:
    return FileStorage(settings.upload_dir)


StorageDep = Annotated[FileStorage, Depends(get_storage)]


def _notify_worker(request: Request) -> None:
    worker = getattr(request.app.state, "worker", None)
    if worker is not None:
        worker.notify()


def _get_source(session: Session, source_id: uuid.UUID) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise AppError(404, "not_found", "That source doesn't exist (it may have been deleted).")
    return source


@router.get("/meta", response_model=MetaResponse)
def meta(session: SessionDep, settings: SettingsDep) -> MetaResponse:
    try:
        session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    semantic = get_embedding_provider(settings) is not None
    return MetaResponse(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        max_upload_bytes=settings.max_upload_bytes,
        max_note_chars=settings.max_note_chars,
        accepted_extensions=sorted(EXTENSIONS),
        capabilities=Capabilities(
            keyword_search=True,
            semantic_search=semantic,
            grounded_chat=False,
            memory_extraction=False,
        ),
    )


@router.post("/sources/notes", response_model=SourceSummary, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate, request: Request, session: SessionDep, settings: SettingsDep
) -> Source:
    source = ingestion.create_note(session, settings, payload.body, payload.title)
    _notify_worker(request)
    return source


@router.post("/sources/files", response_model=SourceSummary, status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File()],
) -> Source:
    buffer = bytearray()
    while chunk := await file.read(READ_CHUNK):
        buffer.extend(chunk)
        if len(buffer) > settings.max_upload_bytes:
            raise file_too_large(settings.max_upload_bytes)
    source = ingestion.create_file_source(session, settings, storage, file.filename, bytes(buffer))
    _notify_worker(request)
    return source


@router.get("/sources", response_model=SourceList)
def list_sources(
    session: SessionDep,
    status_filter: Annotated[SourceStatus | None, Query(alias="status")] = None,
    kind: SourceKind | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SourceList:
    filters = []
    if status_filter:
        filters.append(Source.status == status_filter)
    if kind:
        filters.append(Source.kind == kind)
    total = session.scalar(select(func.count()).select_from(Source).where(*filters)) or 0
    items = session.scalars(
        select(Source)
        .where(*filters)
        .order_by(Source.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return SourceList(items=[SourceSummary.model_validate(s) for s in items], total=total)


@router.get("/sources/{source_id}", response_model=SourceDetail)
def get_source(source_id: uuid.UUID, session: SessionDep) -> Source:
    source = session.scalar(
        select(Source).where(Source.id == source_id).options(selectinload(Source.chunks))
    )
    if source is None:
        raise AppError(404, "not_found", "That source doesn't exist (it may have been deleted).")
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, session: SessionDep, storage: StorageDep) -> Response:
    ingestion.delete_source(session, storage, _get_source(session, source_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sources/{source_id}/retry", response_model=SourceSummary)
def retry_source(source_id: uuid.UUID, request: Request, session: SessionDep) -> Source:
    source = ingestion.retry_source(session, _get_source(session, source_id))
    _notify_worker(request)
    return source


@router.get("/search", response_model=SearchResponse)
def search_sources(
    session: SessionDep,
    settings: SettingsDep,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchResponse:
    query = q.strip()
    if not query:
        raise AppError(422, "empty_query", "Type something to search for.")
    result = search(session, query, limit=limit, offset=offset)
    return SearchResponse.model_validate(
        {
            "query": query,
            "mode": "keyword",
            "semantic_available": get_embedding_provider(settings) is not None,
            "total": result.total,
            "query_has_terms": result.query_has_terms,
            "hits": [
                hit.__dict__ | {"snippet": [p.__dict__ for p in hit.snippet]} for hit in result.hits
            ],
        }
    )
