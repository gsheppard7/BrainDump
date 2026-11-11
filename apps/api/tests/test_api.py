from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Chunk, Source, SourceStatus
from app.services.ingestion import claim_next, recover_interrupted
from tests.conftest import make_pdf


def _note(client, body, title=None):
    return client.post("/api/sources/notes", json={"body": body, "title": title})


def _upload(client, name, data):
    return client.post(
        "/api/sources/files", files={"file": (name, data, "application/octet-stream")}
    )


def test_meta_reports_keyword_only(client):
    body = client.get("/api/meta").json()
    assert body["database"] is True
    assert body["capabilities"] == {
        "keyword_search": True,
        "semantic_search": False,
        "grounded_chat": False,
        "memory_extraction": False,
    }
    assert ".pdf" in body["accepted_extensions"]


def test_note_lifecycle_pending_to_ready_and_searchable(client, process):
    res = _note(client, "Met Priya about the greenhouse irrigation budget.", "Garden sync")
    assert res.status_code == 201
    note = res.json()
    assert note["status"] == "pending"
    assert note["title"] == "Garden sync"

    assert process() == 1
    detail = client.get(f"/api/sources/{note['id']}").json()
    assert detail["status"] == "ready"
    assert detail["text_content"].startswith("Met Priya")
    assert len(detail["chunks"]) == 1

    search = client.get("/api/search", params={"q": "irrigation"}).json()
    assert search["mode"] == "keyword"
    assert search["semantic_available"] is False
    assert search["total"] == 1
    hit = search["hits"][0]
    assert hit["source_id"] == note["id"]
    assert {"text": "irrigation", "highlight": True} in hit["snippet"]


def test_note_title_is_derived_and_validated(client):
    assert _note(client, "# Reading list\n- Dune").json()["title"] == "Reading list"
    res = _note(client, "   \n  ")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "empty_note"


def test_pdf_upload_processing_and_page_citations(client, process):
    pdf = make_pdf(
        ["Introduction to sourdough starters.", "Hydration ratios and the autolyse step."],
        title="Bread Notes",
    )
    res = _upload(client, "bread.pdf", pdf)
    assert res.status_code == 202
    src = res.json()
    assert src["status"] == "pending"
    assert src["file_type"] == "pdf"

    process()
    detail = client.get(f"/api/sources/{src['id']}").json()
    assert detail["status"] == "ready"
    assert detail["title"] == "Bread Notes"
    assert detail["page_count"] == 2
    assert [c["page"] for c in detail["chunks"]] == [1, 2]

    hit = client.get("/api/search", params={"q": "autolyse"}).json()["hits"][0]
    assert hit["page"] == 2
    chunk = detail["chunks"][hit["chunk_ordinal"]]
    assert "autolyse" in detail["text_content"][chunk["char_start"] : chunk["char_end"]]


def test_markdown_title_from_heading(client, process):
    src = _upload(client, "2026-notes.md", b"# Quarterly goals\n\nShip BrainDump.").json()
    process()
    assert client.get(f"/api/sources/{src['id']}").json()["title"] == "Quarterly goals"


def test_duplicates_are_rejected_with_existing_id(client):
    first = _upload(client, "a.txt", b"same bytes").json()
    res = _upload(client, "renamed.txt", b"same bytes")
    assert res.status_code == 409
    assert res.json()["error"]["details"]["existing_source_id"] == first["id"]

    _note(client, "Same note body")
    assert _note(client, "Same note body\n\n").status_code == 409


def test_unsupported_and_mismatched_files_have_clear_errors(client):
    res = _upload(client, "photo.png", b"\x89PNG")
    assert res.status_code == 415
    assert "aren't supported" in res.json()["error"]["message"]

    res = _upload(client, "fake.pdf", b"hello there")
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "content_mismatch"

    assert client.get("/api/sources").json()["total"] == 0


def test_oversized_upload_rejected(client, settings, storage):
    settings.max_upload_mb = 1
    res = _upload(client, "big.txt", b"a" * (1024 * 1024 + 1))
    assert res.status_code == 413
    assert res.json()["error"]["message"] == ("File is too large. The maximum upload size is 1 MB.")
    assert not any(storage.root.rglob("*")), "nothing should be stored"


def test_oversized_upload_rejected_early_by_content_length(client, settings):
    settings.max_upload_mb = 1
    res = _upload(client, "big.txt", b"a" * (2 * 1024 * 1024))
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "file_too_large"


def test_failed_pdf_shows_reason_and_can_be_retried(client, process, session, settings, storage):
    src = _upload(client, "scan.pdf", make_pdf([""])).json()
    process()
    detail = client.get(f"/api/sources/{src['id']}").json()
    assert detail["status"] == "failed"
    assert detail["error_code"] == "no_extractable_text"
    assert "OCR" in detail["error_message"]

    retried = client.post(f"/api/sources/{src['id']}/retry").json()
    assert retried["status"] == "pending"
    assert retried["error_message"] is None
    assert client.post(f"/api/sources/{src['id']}/retry").status_code == 409


def test_list_filters_and_pagination(client, process):
    _note(client, "first")
    _upload(client, "bad.pdf", make_pdf([""]))
    process()
    _note(client, "third")
    all_items = client.get("/api/sources").json()
    assert all_items["total"] == 3
    assert all_items["items"][0]["title"] == "third"
    assert client.get("/api/sources", params={"status": "failed"}).json()["total"] == 1
    assert client.get("/api/sources", params={"kind": "note"}).json()["total"] == 2
    assert len(client.get("/api/sources", params={"limit": 1}).json()["items"]) == 1
    assert client.get("/api/sources", params={"status": "bogus"}).status_code == 422


def test_delete_removes_chunks_and_file(client, process, session, storage):
    src = _upload(client, "a.txt", b"delete me please").json()
    process()
    assert any(p.is_file() for p in storage.root.rglob("*"))
    assert client.delete(f"/api/sources/{src['id']}").status_code == 204
    assert client.get(f"/api/sources/{src['id']}").status_code == 404
    assert session.scalar(select(Chunk).limit(1)) is None
    assert not any(p.is_file() for p in storage.root.rglob("*"))


def test_search_edge_cases(client, process):
    _note(client, "The meeting about pottery classes", title="Hobbies")
    _note(client, "Pending note mentions pottery too")
    assert process() == 2
    _note(client, "Unprocessed pottery note")

    res = client.get("/api/search", params={"q": "pottery"}).json()
    assert res["total"] == 2, "unprocessed sources must not appear"

    res = client.get("/api/search", params={"q": "hobbies"}).json()
    assert res["total"] == 1, "titles are searchable"

    res = client.get("/api/search", params={"q": "the and of"}).json()
    assert res["query_has_terms"] is False and res["hits"] == []

    assert client.get("/api/search", params={"q": ""}).status_code == 422
    res = client.get("/api/search", params={"q": "   "})
    assert res.status_code == 422 and res.json()["error"]["code"] == "empty_query"

    res = client.get("/api/search", params={"q": '"pottery classes" -pending'}).json()
    assert res["total"] == 1


def test_missing_source_404(client):
    res = client.get("/api/sources/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_interrupted_jobs_are_recovered(client, session, settings):
    src_id = _note(client, "Will be interrupted").json()["id"]
    claimed = claim_next(session, settings)
    assert str(claimed) == src_id
    assert claim_next(session, settings) is None, "claimed job is leased"

    assert recover_interrupted(session) == 1
    assert session.get(Source, claimed).status is SourceStatus.pending


def test_expired_lease_is_reclaimed_and_attempts_capped(client, session, settings):
    _note(client, "Crashy note")
    for _ in range(settings.worker_max_attempts):
        source_id = claim_next(session, settings)
        assert source_id is not None
        source = session.get(Source, source_id)
        source.processing_started_at = datetime.now(UTC) - timedelta(hours=1)
        session.commit()
    assert claim_next(session, settings) is None
    session.expire_all()
    source = session.get(Source, source_id)
    assert source.status is SourceStatus.failed
    assert source.error_code == "too_many_attempts"
