"""Main FastAPI application entry point with static mounts and lifespan hooks."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router, sse_router, ws_router
from app.config import settings
from app.core.broker import broker
from app.core.events import event_bus

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for connection pooling and graceful shutdown."""
    logger.info("Initializing %s in %s mode...", settings.APP_NAME, settings.APP_ENV)
    await event_bus.initialize()
    await broker.connect()
    yield
    logger.info("Shutting down connections...")
    await broker.close()
    await event_bus.close()
    logger.info("Shutdown completed.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Asynchronous distributed pipeline for automated course video generation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API and Real-time Routers
app.include_router(api_router)
app.include_router(sse_router)
app.include_router(ws_router)

# Mount Local Artifact Storage for browser video playback & thumbnail previews
app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_LOCAL_DIR)), name="storage")

# Mount Static Dashboard Assets
static_dir = settings.BASE_DIR / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serves the interactive web test bench and video player dashboard."""
    index_file = settings.BASE_DIR / "app" / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": f"{settings.APP_NAME} is running. Visit /docs for OpenAPI specs."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
