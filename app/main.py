"""Customer Success Digital FTE — FastAPI Application."""

import pathlib
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.middleware import RequestIDMiddleware, LoggingMiddleware
from app.core.exceptions import register_exception_handlers
from app.api.router import api_router
from app.db.database import engine
from app.services.queue_service import QueueService

settings = get_settings()
setup_logging()
logger = get_logger(__name__)

STATIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    logger.info("Starting Customer Success Digital FTE [env=%s]", settings.app_env)
    # Only start Kafka producer if not in demo-only mode
    try:
        await QueueService.start()
    except Exception as e:
        logger.warning("Kafka producer failed to start (demo mode OK): %s", e)
    yield
    logger.info("Shutting down")
    try:
        await QueueService.stop()
    except Exception:
        pass
    await engine.dispose()


app = FastAPI(
    title="Customer Success Digital FTE",
    description="AI-powered customer support agent across Web, Gmail, and WhatsApp (Twilio).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middleware — order matters: outermost first
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Exception handlers
register_exception_handlers(app)

# Routes
app.include_router(api_router)


# Serve frontend dashboard at root
@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the demo dashboard UI."""
    return FileResponse(STATIC_DIR / "index.html")


# Static files (CSS, JS, images) — must be after API routes
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
