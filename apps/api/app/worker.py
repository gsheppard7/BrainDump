"""In-process ingestion worker. Jobs live in Postgres, so restarts lose nothing."""

import logging
import threading

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.services.ingestion import claim_next, process_source, recover_interrupted
from app.services.storage import FileStorage

logger = logging.getLogger(__name__)


def run_once(
    session_factory: sessionmaker[Session], settings: Settings, storage: FileStorage
) -> bool:
    """Process at most one job. Returns True if a job was claimed."""
    with session_factory() as session:
        source_id = claim_next(session, settings)
    if source_id is None:
        return False
    with session_factory() as session:
        process_source(session, settings, storage, source_id)
    return True


def drain(session_factory: sessionmaker[Session], settings: Settings, storage: FileStorage) -> int:
    count = 0
    while run_once(session_factory, settings, storage):
        count += 1
    return count


class IngestionWorker:
    def __init__(
        self, session_factory: sessionmaker[Session], settings: Settings, storage: FileStorage
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._storage = storage
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._session_factory() as session:
            recovered = recover_interrupted(session)
        if recovered:
            logger.info("re-queued %d interrupted sources", recovered)
        self._thread = threading.Thread(target=self._loop, name="ingestion-worker", daemon=True)
        self._thread.start()
        logger.info("ingestion worker started")

    def notify(self) -> None:
        self._wake.set()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                worked = run_once(self._session_factory, self._settings, self._storage)
            except Exception as exc:
                logger.error("worker iteration failed error=%s", type(exc).__name__)
                worked = False
            if not worked:
                self._wake.wait(self._settings.worker_poll_seconds)
                self._wake.clear()
