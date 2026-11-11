"""Load sample data through the normal ingestion path. Idempotent: duplicates are skipped.

Usage: uv run python -m app.seed   (or: docker compose exec api python -m app.seed)
"""

import json
from pathlib import Path

from app.config import get_settings
from app.db import get_session_factory
from app.errors import AppError
from app.services.ingestion import create_file_source, create_note
from app.services.storage import FileStorage
from app.worker import drain

SEED_DIR = Path(__file__).resolve().parents[1] / "seed"


def main() -> None:
    settings = get_settings()
    storage = FileStorage(settings.upload_dir)
    factory = get_session_factory()
    created = skipped = 0

    with factory() as session:
        for note in json.loads((SEED_DIR / "notes.json").read_text()):
            try:
                create_note(session, settings, note["body"], note["title"])
                created += 1
            except AppError as exc:
                if exc.code != "duplicate":
                    raise
                skipped += 1
        for path in sorted(SEED_DIR.iterdir()):
            if path.name == "notes.json" or path.name.startswith("."):
                continue
            try:
                create_file_source(session, settings, storage, path.name, path.read_bytes())
                created += 1
            except AppError as exc:
                if exc.code != "duplicate":
                    raise
                skipped += 1

    processed = drain(factory, settings, storage)
    print(f"seed: created={created} skipped_duplicates={skipped} processed={processed}")


if __name__ == "__main__":
    main()
