"""In-process background worker. Jobs live in Postgres, so restarts lose nothing.

Ingestion (parse, chunk, keyword index) always runs first; semantic indexing (embeddings)
runs when the ingestion queue is empty and backs off while the AI provider is unavailable.
"""

import logging
import threading
import time

from sqlalchemy.orm import Session, sessionmaker

from app.ai import registry
from app.config import Settings
from app.services.indexing import EmbeddingFailed, embed_next, requeue_stale
from app.services.ingestion import claim_next, process_source, recover_interrupted
from app.services.storage import FileStorage

logger = logging.getLogger(__name__)

EMBEDDING_BACKOFF_SECONDS = 30.0


def run_once(
    session_factory: sessionmaker[Session], settings: Settings, storage: FileStorage
) -> bool:
    """Process at most one ingestion job. Returns True if a job was claimed."""
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


def drain_embeddings(session_factory: sessionmaker[Session], settings: Settings) -> int:
    provider = registry.get_embedding_provider(settings)
    if provider is None:
        return 0
    count = 0
    while embed_next(session_factory, provider, settings.embedding_batch_size):
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
        self._embed_after = 0.0

    def start(self) -> None:
        with self._session_factory() as session:
            recovered = recover_interrupted(session)
            provider = registry.get_embedding_provider(self._settings)
            queued = requeue_stale(session, provider.model) if provider else 0
        if recovered:
            logger.info("re-queued %d interrupted sources", recovered)
        if queued:
            logger.info("queued %d sources for semantic indexing", queued)
        self._thread = threading.Thread(target=self._loop, name="ingestion-worker", daemon=True)
        self._thread.start()
        logger.info("background worker started")

    def notify(self) -> None:
        self._wake.set()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)

    def _embed_once(self) -> bool:
        provider = registry.get_embedding_provider(self._settings)
        if provider is None or time.monotonic() < self._embed_after:
            return False
        try:
            return embed_next(self._session_factory, provider, self._settings.embedding_batch_size)
        except EmbeddingFailed as exc:
            logger.warning(
                "semantic indexing paused for %ds error=%s", EMBEDDING_BACKOFF_SECONDS, exc
            )
            self._embed_after = time.monotonic() + EMBEDDING_BACKOFF_SECONDS
            return False

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                worked = run_once(self._session_factory, self._settings, self._storage)
                if not worked:
                    worked = self._embed_once()
            except Exception as exc:
                logger.error("worker iteration failed error=%s", type(exc).__name__)
                worked = False
            if not worked:
                self._wake.wait(self._settings.worker_poll_seconds)
                self._wake.clear()
