"""Turn raw bytes into normalised text segments. Content is treated as inert data."""

import io
import logging
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from app.errors import IngestionError
from app.models import FileType
from app.services.text import normalize_text
from app.services.validation import decode_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment:
    text: str
    page: int | None = None


@dataclass(frozen=True)
class ParsedDocument:
    segments: list[Segment]
    page_count: int | None = None
    title: str | None = None


def parse_file(data: bytes, file_type: FileType, max_pdf_pages: int) -> ParsedDocument:
    if file_type is FileType.pdf:
        return parse_pdf(data, max_pdf_pages)
    text = decode_text(data)
    if text is None:
        raise IngestionError("unreadable_text", "The file couldn't be decoded as UTF-8 text.")
    text = normalize_text(text)
    if not text:
        raise IngestionError("no_text", "The file contains no text.")
    return ParsedDocument(segments=[Segment(text)])


def parse_pdf(data: bytes, max_pages: int) -> ParsedDocument:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise IngestionError(
                "pdf_encrypted", "This PDF is password-protected. Remove the password and retry."
            )
        page_count = len(reader.pages)
    except IngestionError:
        raise
    except (FileNotDecryptedError, NotImplementedError) as exc:
        raise IngestionError(
            "pdf_encrypted", "This PDF is encrypted in a way BrainDump can't open."
        ) from exc
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise IngestionError(
            "pdf_corrupt", "This PDF appears to be damaged and couldn't be read."
        ) from exc

    if page_count == 0:
        raise IngestionError("no_text", "This PDF has no pages.")
    if page_count > max_pages:
        raise IngestionError(
            "pdf_too_many_pages", f"This PDF has {page_count} pages; the limit is {max_pages}."
        )

    segments: list[Segment] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception as exc:  # pypdf raises many types on malformed pages
            logger.warning("pdf page extraction failed page=%d error=%s", index, type(exc).__name__)
            continue
        text = normalize_text(raw)
        if text:
            segments.append(Segment(text=text, page=index))

    if not segments:
        raise IngestionError(
            "no_extractable_text",
            "No selectable text was found in this PDF. It may be a scanned image — "
            "OCR isn't supported yet.",
        )

    title = None
    try:
        meta_title = reader.metadata.title if reader.metadata else None
        if isinstance(meta_title, str) and 2 < len(meta_title.strip()) <= 200:
            title = normalize_text(meta_title)
    except Exception:
        title = None
    return ParsedDocument(segments=segments, page_count=page_count, title=title)
