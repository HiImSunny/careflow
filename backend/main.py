"""
CareFlow Orchestrator — FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routers import cases as cases_router
from backend.routers import orchestrate as orchestrate_router

app = FastAPI(
    title="CareFlow Orchestrator",
    description="Multi-agent clinical decision support platform.",
    version="0.1.0",
)

# Allow all origins for local development; tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    """Initialize the database schema on application startup."""
    init_db()


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

app.include_router(orchestrate_router.router, prefix="/api")
app.include_router(cases_router.router, prefix="/api")

# Chat router is added lazily — it will be implemented in a later task.
try:
    from backend.routers import chat as chat_router  # noqa: F401

    app.include_router(chat_router.router, prefix="/api")
except ImportError:
    pass

# Speech router for real-time audio transcription via WebSocket.
try:
    from backend.routers import speech as speech_router  # noqa: F401

    app.include_router(speech_router.router, prefix="/api")
except ImportError:
    pass


@app.get("/health")
async def health_check() -> dict:
    """Simple health-check endpoint."""
    return {"status": "ok"}
