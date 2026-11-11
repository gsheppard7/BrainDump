"""Paragraph-aware chunking that preserves exact character offsets into the source text."""

import re
from dataclasses import dataclass

from app.services.parsing import Segment

SEGMENT_SEPARATOR = "\n\n"
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"[.!?]\s")


@dataclass(frozen=True)
class ChunkSpan:
    start: int
    end: int
    page: int | None


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    pos = 0
    for match in _PARAGRAPH_BREAK.finditer(text):
        spans.append((pos, match.start()))
        pos = match.end()
    spans.append((pos, len(text)))
    return [_trim(text, s, e) for s, e in spans if text[s:e].strip()]


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_long(text: str, start: int, end: int, max_chars: int) -> list[tuple[int, int]]:
    """Split an oversized paragraph, preferring sentence boundaries, then whitespace."""
    pieces: list[tuple[int, int]] = []
    while end - start > max_chars:
        window = text[start : start + max_chars]
        cut = -1
        for match in _SENTENCE_END.finditer(window):
            if match.end() > max_chars // 2:
                cut = match.end()
        if cut == -1:
            ws = window.rfind(" ", max_chars // 2)
            cut = ws + 1 if ws != -1 else max_chars
        pieces.append(_trim(text, start, start + cut))
        start, _ = _trim(text, start + cut, end)
    if start < end:
        pieces.append((start, end))
    return [p for p in pieces if p[1] > p[0]]


def chunk_text(text: str, target_chars: int = 1000, max_chars: int = 1500) -> list[tuple[int, int]]:
    pieces: list[tuple[int, int]] = []
    for start, end in _paragraph_spans(text):
        pieces.extend(_split_long(text, start, end, max_chars))

    chunks: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for start, end in pieces:
        if current is None:
            current = (start, end)
        elif end - current[0] <= target_chars:
            current = (current[0], end)
        else:
            chunks.append(current)
            current = (start, end)
    if current is not None:
        chunks.append(current)
    return chunks


def assemble(segments: list[Segment]) -> tuple[str, list[ChunkSpan]]:
    """Join segments into one document and chunk each segment (chunks never cross pages)."""
    parts: list[str] = []
    spans: list[ChunkSpan] = []
    offset = 0
    for i, segment in enumerate(segments):
        if i:
            parts.append(SEGMENT_SEPARATOR)
            offset += len(SEGMENT_SEPARATOR)
        for start, end in chunk_text(segment.text):
            spans.append(ChunkSpan(offset + start, offset + end, segment.page))
        parts.append(segment.text)
        offset += len(segment.text)
    return "".join(parts), spans
