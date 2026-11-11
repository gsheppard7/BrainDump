import codecs

import pytest

from app.errors import AppError, IngestionError
from app.models import FileType
from app.services.parsing import parse_file
from app.services.validation import sanitize_filename, validate_upload
from tests.conftest import make_pdf

MB = 1024 * 1024


@pytest.mark.parametrize(
    ("name", "expected"),
    [("notes.md", FileType.markdown), ("A.MARKDOWN", FileType.markdown), ("x.txt", FileType.text)],
)
def test_accepts_text_types(name, expected):
    assert validate_upload(name, b"hello", MB).file_type is expected


def test_accepts_real_pdf():
    assert validate_upload("doc.pdf", make_pdf(["hi"]), MB).file_type is FileType.pdf


@pytest.mark.parametrize("name", ["photo.png", "doc.docx", "script.sh", "noextension"])
def test_rejects_unsupported_extensions(name):
    with pytest.raises(AppError) as exc:
        validate_upload(name, b"data", MB)
    assert exc.value.status_code == 415
    assert exc.value.code == "unsupported_file_type"


def test_rejects_fake_pdf():
    with pytest.raises(AppError) as exc:
        validate_upload("evil.pdf", b"MZ\x90\x00 not a pdf", MB)
    assert exc.value.code == "content_mismatch"


def test_rejects_binary_disguised_as_text():
    with pytest.raises(AppError) as exc:
        validate_upload("notes.txt", b"\x89PNG\r\n\x1a\n\x00\x00\x00", MB)
    assert exc.value.code == "content_mismatch"


def test_rejects_empty_and_whitespace_files():
    for data in (b"", b"   \n\n"):
        with pytest.raises(AppError) as exc:
            validate_upload("a.txt", data, MB)
        assert exc.value.code == "empty_file"


def test_rejects_oversized():
    with pytest.raises(AppError) as exc:
        validate_upload("a.txt", b"x" * (MB + 1), MB)
    assert exc.value.status_code == 413
    assert "1 MB" in exc.value.message


def test_accepts_utf16_with_bom():
    data = codecs.BOM_UTF16_LE + "héllo".encode("utf-16-le")
    assert validate_upload("a.txt", data, MB).file_type is FileType.text
    assert parse_file(data, FileType.text, 10).segments[0].text == "héllo"


def test_sanitize_filename_strips_paths_and_controls():
    assert sanitize_filename("../../etc/passwd.txt") == "passwd.txt"
    assert sanitize_filename("C:\\Users\\me\\notes.md") == "notes.md"
    assert sanitize_filename("bad\x00name.txt") == "badname.txt"
    assert sanitize_filename(None) == "upload"


def test_parse_pdf_extracts_pages_and_title():
    parsed = parse_file(
        make_pdf(["Alpha page content", "", "Gamma page content"], title="My Paper"),
        FileType.pdf,
        100,
    )
    assert parsed.page_count == 3
    assert parsed.title == "My Paper"
    assert [(s.page, s.text) for s in parsed.segments] == [
        (1, "Alpha page content"),
        (3, "Gamma page content"),
    ]


def test_parse_pdf_errors_are_user_facing():
    cases = {
        "pdf_encrypted": make_pdf(["secret"], password="pw"),
        "pdf_corrupt": b"%PDF-1.7\n garbage garbage",
        "no_extractable_text": make_pdf([""]),
    }
    for code, data in cases.items():
        with pytest.raises(IngestionError) as exc:
            parse_file(data, FileType.pdf, 100)
        assert exc.value.code == code, code


def test_parse_pdf_page_limit():
    with pytest.raises(IngestionError) as exc:
        parse_file(make_pdf(["a", "b", "c"]), FileType.pdf, 2)
    assert exc.value.code == "pdf_too_many_pages"
