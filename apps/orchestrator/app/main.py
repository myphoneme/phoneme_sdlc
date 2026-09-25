"""
Phoneme SDLC Platform — backend entrypoint.

Run locally:      uvicorn app.main:app --reload --port 8080
Run on staging:    see src/backend/README.md (systemd unit / process manager
                    per BRD/PRD Section 18.7 — one process per project).
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .routers import discovery, wizard, brdprd

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Phoneme SDLC Platform API",
    description="Idea-to-BRD/PRD Wizard backend — Concept-to-Launch SDLC Stage 1",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(discovery.router)
app.include_router(wizard.router)
app.include_router(brdprd.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "commercial_provider": config.COMMERCIAL_PROVIDER,
        "ollama_url": config.OLLAMA_URL,
    }
