import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import get_session_factory
from app.errors import install_error_handlers
from app.routes import router
from app.services.storage import FileStorage
from app.services.validation import file_too_large
from app.worker import IngestionWorker

MULTIPART_OVERHEAD = 64 * 1024

logger = logging.getLogger("braindump.http")


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # The default access log includes query strings (i.e. search terms). Ours doesn't.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    worker = None
    if settings.worker_enabled:
        worker = IngestionWorker(get_session_factory(), settings, FileStorage(settings.upload_dir))
        worker.start()
    app.state.worker = worker
    yield
    if worker:
        worker.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="BrainDump API", version="0.1.0", lifespan=lifespan)
    install_error_handlers(app)
    app.include_router(router)

    @app.middleware("http")
    async def reject_oversized_and_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        length = request.headers.get("content-length")
        limit = settings.max_upload_bytes + MULTIPART_OVERHEAD
        if request.method == "POST" and length and length.isdigit() and int(length) > limit:
            err = file_too_large(settings.max_upload_bytes)
            response: Response = JSONResponse(
                status_code=err.status_code,
                content={
                    "error": {"code": err.code, "message": err.message, "details": err.details}
                },
            )
        else:
            response = await call_next(request)
        logger.info(
            "%s %s %d %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
