"""Persist Ask questions and answers so they can be reopened later."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import ChatMessage, ChatRole, ChatSession
from app.services.ask import AskMode


def title_from_question(question: str, limit: int = 80) -> str:
    cleaned = re.sub(r"\s+", " ", question).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def create_session(session: Session, question: str, mode: AskMode) -> ChatSession:
    row = ChatSession(title=title_from_question(question), mode=mode)
    session.add(row)
    session.flush()
    session.add(ChatMessage(session_id=row.id, role=ChatRole.user, content=question))
    session.flush()
    return row


def save_assistant(
    session: Session,
    session_id: uuid.UUID,
    *,
    content: str,
    citations: list[int] | None = None,
    passages: list[dict] | None = None,
    grounded: bool | None = None,
    model: str | None = None,
    notice: str | None = None,
    error_message: str | None = None,
) -> ChatMessage:
    chat = session.get(ChatSession, session_id)
    if chat is None:
        raise LookupError("chat session missing")
    message = ChatMessage(
        session_id=session_id,
        role=ChatRole.assistant,
        content=content,
        citations=citations,
        passages=passages,
        grounded=grounded,
        model=model,
        notice=notice,
        error_message=error_message,
    )
    chat.updated_at = datetime.now(UTC)
    session.add(message)
    session.flush()
    return message


def list_sessions(
    session: Session, *, limit: int = 50, offset: int = 0
) -> tuple[list[ChatSession], int]:
    total = session.scalar(select(func.count()).select_from(ChatSession)) or 0
    items = session.scalars(
        select(ChatSession)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(items), total


def get_session(session: Session, session_id: uuid.UUID) -> ChatSession | None:
    return session.scalar(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))
    )


def delete_session(session: Session, chat: ChatSession) -> None:
    session.delete(chat)
    session.flush()
