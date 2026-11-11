import json
import logging
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai import registry
from app.config import Settings, get_settings
from app.db import get_session, get_session_factory
from app.errors import AppError
from app.models import EmbeddingStatus, Source, SourceKind, SourceStatus
from app.schemas import (
    AIInfo,
    AskRequest,
    Capabilities,
    ChatSessionDetail,
    ChatSessionList,
    ChatSessionSummary,
    GraphResponse,
    IndexStats,
    MetaResponse,
    NoteCreate,
    SearchResponse,
    SourceDetail,
    SourceList,
    SourceSummary,
)
from app.services import chats, ingestion
from app.services.ask import AskMode, gather_context, stream_answer
from app.services.graph import build_graph, graph_as_dict
from app.services.search import search
from app.services.storage import FileStorage
from app.services.validation import EXTENSIONS, file_too_large

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

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
        counts = session.execute(
            select(
                func.count(),
                func.count().filter(Source.embedding_status == EmbeddingStatus.done),
                func.count().filter(Source.embedding_status == EmbeddingStatus.pending),
            ).where(Source.status == SourceStatus.ready)
        ).one()
        db_ok = True
    except Exception:
        counts = (0, 0, 0)
        db_ok = False
    ai = registry.ai_status(settings)
    return MetaResponse(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        max_upload_bytes=settings.max_upload_bytes,
        max_note_chars=settings.max_note_chars,
        accepted_extensions=sorted(EXTENSIONS),
        capabilities=Capabilities(
            keyword_search=True,
            semantic_search=ai.embeddings_ready,
            grounded_chat=ai.chat_ready,
            memory_extraction=False,
        ),
        ai=AIInfo(
            provider=ai.provider,
            location=ai.location,
            embedding_model=ai.embedding_model,
            chat_model=ai.chat_model,
            reachable=ai.reachable,
            message=ai.message,
        ),
        index=IndexStats(
            ready_sources=counts[0], semantic_indexed=counts[1], semantic_pending=counts[2]
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
    embedder = registry.get_embedding_provider(settings)
    vector, notice = None, None
    if embedder is not None:
        try:
            vector = embedder.embed_query(query)
        except Exception as exc:
            logger.warning("query embedding failed error=%s", type(exc).__name__)
            notice = (
                "Meaning-based matching is unavailable right now; showing keyword matches only."
            )
    result = search(
        session,
        query,
        limit=limit,
        offset=offset,
        query_vector=vector,
        min_similarity=settings.vector_min_similarity,
        candidates=settings.retrieval_candidates,
    )
    return SearchResponse.model_validate(
        {
            "query": query,
            "mode": "hybrid" if vector is not None else "keyword",
            "semantic_available": embedder is not None,
            "notice": notice,
            "total": result.total,
            "query_has_terms": result.query_has_terms,
            "hits": [
                hit.__dict__ | {"snippet": [p.__dict__ for p in hit.snippet]} for hit in result.hits
            ],
        }
    )


def _ask_events(
    *,
    question: str,
    mode: AskMode,
    passages: list,
    notice: str | None,
    chat,
) -> Iterator[dict[str, Any]]:
    """Stream Ask events and persist the turn to chat history."""
    factory = get_session_factory()
    with factory() as db:
        chat_session = chats.create_session(db, question, mode)
        db.commit()
        session_id = chat_session.id
    yield {"type": "session", "id": str(session_id)}

    answer_parts: list[str] = []
    passages_payload: list[dict] | None = None
    model: str | None = None
    notice_out = notice
    finished = False
    try:
        for event in stream_answer(chat, question, mode, passages, notice):
            kind = event["type"]
            if kind == "meta":
                model = event.get("model")
                notice_out = event.get("notice")
            elif kind == "context":
                passages_payload = event.get("passages")
            elif kind == "delta":
                answer_parts.append(event["text"])
            elif kind == "done":
                with factory() as db:
                    chats.save_assistant(
                        db,
                        session_id,
                        content="".join(answer_parts),
                        citations=event.get("citations"),
                        passages=passages_payload,
                        grounded=event.get("grounded"),
                        model=model,
                        notice=notice_out,
                    )
                    db.commit()
                finished = True
                yield {**event, "session_id": str(session_id)}
                continue
            elif kind == "error":
                with factory() as db:
                    chats.save_assistant(
                        db,
                        session_id,
                        content="".join(answer_parts),
                        passages=passages_payload,
                        model=model,
                        notice=notice_out,
                        error_message=event.get("message"),
                    )
                    db.commit()
                finished = True
            yield event
    finally:
        if not finished:
            with factory() as db:
                chats.save_assistant(
                    db,
                    session_id,
                    content="".join(answer_parts),
                    passages=passages_payload,
                    model=model,
                    notice=notice_out,
                    error_message="Stopped." if answer_parts else "Interrupted before an answer.",
                )
                db.commit()


@router.post("/ask")
def ask(payload: AskRequest, session: SessionDep, settings: SettingsDep) -> StreamingResponse:
    """Streams newline-delimited JSON events: session, meta, context, delta*, then done or error."""
    question = payload.question.strip()
    if not question:
        raise AppError(422, "empty_question", "Type a question or request first.")
    chat = registry.get_chat_provider(settings)
    if chat is None:
        raise AppError(
            503,
            "ai_disabled",
            "Ask needs an AI model. Set CHAT_PROVIDER=ollama in .env and restart the API.",
        )
    passages, notice = gather_context(
        session, settings, question, payload.mode, registry.get_embedding_provider(settings)
    )
    events = _ask_events(
        question=question, mode=payload.mode, passages=passages, notice=notice, chat=chat
    )
    return StreamingResponse(
        (json.dumps(event) + "\n" for event in events),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/chats", response_model=ChatSessionList)
def list_chats(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChatSessionList:
    items, total = chats.list_sessions(session, limit=limit, offset=offset)
    return ChatSessionList(
        items=[ChatSessionSummary.model_validate(item) for item in items], total=total
    )


@router.get("/chats/{chat_id}", response_model=ChatSessionDetail)
def get_chat(chat_id: uuid.UUID, session: SessionDep) -> ChatSessionDetail:
    chat = chats.get_session(session, chat_id)
    if chat is None:
        raise AppError(404, "not_found", "That conversation doesn't exist.")
    return ChatSessionDetail.model_validate(chat)


@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat(chat_id: uuid.UUID, session: SessionDep) -> Response:
    chat = chats.get_session(session, chat_id)
    if chat is None:
        raise AppError(404, "not_found", "That conversation doesn't exist.")
    chats.delete_session(session, chat)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/graph", response_model=GraphResponse)
def knowledge_graph(session: SessionDep, settings: SettingsDep) -> GraphResponse:
    graph = build_graph(
        session,
        min_similarity=settings.graph_min_similarity,
        max_edges=settings.graph_max_edges,
    )
    return GraphResponse.model_validate(graph_as_dict(graph))
