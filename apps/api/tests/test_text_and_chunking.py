from app.services.chunking import SEGMENT_SEPARATOR, assemble, chunk_text
from app.services.parsing import Segment
from app.services.search import parse_headline
from app.services.text import derive_title, normalize_text


def test_normalize_text_strips_controls_and_collapses_whitespace():
    raw = "Hello\r\nworld\x00\x02  \n\n\n\n\nNext\t para  \n"
    assert normalize_text(raw) == "Hello\nworld\n\nNext\t para"


def test_derive_title_prefers_heading_and_truncates():
    assert derive_title("\n\n# Weekly review\nbody", "x") == "Weekly review"
    assert derive_title("", "Fallback") == "Fallback"
    long = derive_title("a" * 200, "x", max_len=50)
    assert len(long) == 50 and long.endswith("…")


def test_chunk_offsets_are_exact_and_bounded():
    paragraphs = [f"Paragraph {i}. " + ("word " * 60).strip() for i in range(30)]
    text = "\n\n".join(paragraphs)
    spans = chunk_text(text, target_chars=1000, max_chars=1500)
    assert len(spans) > 1
    for start, end in spans:
        piece = text[start:end]
        assert piece == piece.strip()
        assert len(piece) <= 1500
    covered = "".join(text[s:e] for s, e in spans).replace("\n", "")
    assert covered == text.replace("\n", "")


def test_long_paragraph_is_split_on_sentence_boundaries():
    text = " ".join(f"Sentence number {i} is here." for i in range(200))
    spans = chunk_text(text, target_chars=1000, max_chars=1500)
    assert len(spans) > 2
    for start, end in spans[:-1]:
        assert text[start:end].endswith(".")
        assert end - start <= 1500


def test_assemble_never_crosses_pages_and_offsets_match():
    segments = [Segment("Page one text.", page=1), Segment("Page two text.", page=2)]
    full, spans = assemble(segments)
    assert full == "Page one text." + SEGMENT_SEPARATOR + "Page two text."
    assert [(full[s.start : s.end], s.page) for s in spans] == [
        ("Page one text.", 1),
        ("Page two text.", 2),
    ]


def test_parse_headline_segments():
    parts = parse_headline("a \x02fox\x03 and \x02dog\x03")
    assert [(p.text, p.highlight) for p in parts] == [
        ("a ", False),
        ("fox", True),
        (" and ", False),
        ("dog", True),
    ]
