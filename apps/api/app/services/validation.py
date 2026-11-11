"""Upload validation: extension allow-list plus content sniffing. Never trusts Content-Type."""

import codecs
from dataclasses import dataclass
from pathlib import PurePath

from app.errors import AppError
from app.models import FileType

EXTENSIONS: dict[str, FileType] = {
    ".pdf": FileType.pdf,
    ".md": FileType.markdown,
    ".markdown": FileType.markdown,
    ".txt": FileType.text,
}
SUPPORTED_DESCRIPTION = "PDF (.pdf), Markdown (.md, .markdown), or plain text (.txt)"


@dataclass(frozen=True)
class ValidatedUpload:
    file_type: FileType
    filename: str


def sanitize_filename(raw: str | None) -> str:
    name = PurePath((raw or "").replace("\\", "/")).name
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:255] or "upload"


def decode_text(data: bytes) -> str | None:
    """Decode UTF-8 (optionally BOM) or BOM-marked UTF-16. Returns None for binary data."""
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            text = data.decode("utf-16")
        except UnicodeDecodeError:
            return None
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
    if "\x00" in text:
        return None
    return text


def validate_upload(filename: str | None, data: bytes, max_bytes: int) -> ValidatedUpload:
    name = sanitize_filename(filename)
    suffix = PurePath(name).suffix.lower()
    file_type = EXTENSIONS.get(suffix)
    if file_type is None:
        raise AppError(
            415,
            "unsupported_file_type",
            f"'{suffix or 'no extension'}' files aren't supported. "
            f"Upload a {SUPPORTED_DESCRIPTION}.",
            {"supported_extensions": sorted(EXTENSIONS)},
        )
    if len(data) > max_bytes:
        raise file_too_large(max_bytes)
    if len(data) == 0:
        raise AppError(400, "empty_file", "The file is empty.")

    if file_type is FileType.pdf:
        if b"%PDF-" not in data[:1024]:
            raise AppError(
                415, "content_mismatch", "This file has a .pdf extension but isn't a valid PDF."
            )
    else:
        text = decode_text(data)
        if text is None:
            raise AppError(
                415,
                "content_mismatch",
                "This file doesn't look like plain text. Text and Markdown files must be "
                "UTF-8 encoded.",
            )
        if not text.strip():
            raise AppError(400, "empty_file", "The file contains no text.")
    return ValidatedUpload(file_type=file_type, filename=name)


def file_too_large(max_bytes: int) -> AppError:
    mb = max_bytes / (1024 * 1024)
    return AppError(
        413,
        "file_too_large",
        f"File is too large. The maximum upload size is {mb:g} MB.",
        {"max_bytes": max_bytes},
    )
