import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import EmbeddingStatus, FileType, SourceKind, SourceStatus
from app.services.ask import AskMode


class NoteCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    body: str = Field(min_length=1)


class SourceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: SourceKind
    file_type: FileType | None
    title: str
    original_filename: str | None
    size_bytes: int
    status: SourceStatus
    embedding_status: EmbeddingStatus | None
    error_code: str | None
    error_message: str | None
    char_count: int | None
    page_count: int | None
    created_at: datetime
    processed_at: datetime | None


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ordinal: int
    char_start: int
    char_end: int
    page: int | None


class SourceDetail(SourceSummary):
    text_content: str | None
    chunks: list[ChunkOut]


class SourceList(BaseModel):
    items: list[SourceSummary]
    total: int


class SnippetPartOut(BaseModel):
    text: str
    highlight: bool


class SearchHitOut(BaseModel):
    source_id: uuid.UUID
    title: str
    kind: SourceKind
    file_type: FileType | None
    created_at: datetime
    chunk_id: uuid.UUID
    chunk_ordinal: int
    page: int | None
    rank: float
    match_count: int
    match_reasons: list[Literal["keyword", "semantic"]]
    snippet: list[SnippetPartOut]


class SearchResponse(BaseModel):
    query: str
    mode: Literal["keyword", "hybrid"]
    semantic_available: bool
    notice: str | None
    total: int
    query_has_terms: bool
    hits: list[SearchHitOut]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: AskMode = "recall"


class Capabilities(BaseModel):
    keyword_search: bool
    semantic_search: bool
    grounded_chat: bool
    memory_extraction: bool


class AIInfo(BaseModel):
    provider: str
    location: str
    embedding_model: str | None
    chat_model: str | None
    reachable: bool
    message: str | None


class IndexStats(BaseModel):
    ready_sources: int
    semantic_indexed: int
    semantic_pending: int


class MetaResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    max_upload_bytes: int
    max_note_chars: int
    accepted_extensions: list[str]
    capabilities: Capabilities
    ai: AIInfo
    index: IndexStats
