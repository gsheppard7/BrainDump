import os
import shutil
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="braindump-test-"))
_BASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://braindump:braindump@localhost:5433/braindump_test",
)
os.environ["DATABASE_URL"] = _BASE_URL
os.environ["DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["WORKER_ENABLED"] = "false"
os.environ["EMBEDDING_PROVIDER"] = "none"
os.environ["CHAT_PROVIDER"] = "none"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from fpdf import FPDF  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from alembic import command  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.services.storage import FileStorage  # noqa: E402
from app.worker import drain  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]


def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": parsed.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{parsed.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def database():
    _ensure_database(_BASE_URL)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.attributes["database_url"] = _BASE_URL
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_state(database):
    settings = get_settings()
    original_max = settings.max_upload_mb
    with get_session_factory()() as session:
        session.execute(text("TRUNCATE chat_messages, chat_sessions, chunks, sources CASCADE"))
        session.commit()
    shutil.rmtree(settings.upload_dir, ignore_errors=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    yield
    settings.max_upload_mb = original_max


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def session():
    with get_session_factory()() as s:
        yield s


@pytest.fixture
def storage(settings):
    return FileStorage(settings.upload_dir)


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def process(settings, storage):
    """Run the ingestion worker synchronously until the queue is empty."""

    def _run() -> int:
        return drain(get_session_factory(), settings, storage)

    return _run


def make_pdf(pages: list[str], title: str | None = None, password: str | None = None) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    if title:
        pdf.set_title(title)
    if password:
        pdf.set_encryption(owner_password="owner", user_password=password)
    for body in pages:
        pdf.add_page()
        if body:
            pdf.multi_cell(0, 8, body)
    return bytes(pdf.output())
