import re
import unicodedata

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRAILING_WS = re.compile(r"[ \t]+\n")
_MANY_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Canonical form used for storage, hashing, and indexing.

    Control characters are stripped so they can be used as safe highlight markers in search.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    text = _TRAILING_WS.sub("\n", text)
    text = _MANY_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def derive_title(text: str, fallback: str, max_len: int = 120) -> str:
    """First markdown heading or first non-empty line, else the fallback."""
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line if len(line) <= max_len else line[: max_len - 1].rstrip() + "…"
    return fallback
