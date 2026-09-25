"""
Phoneme SDLC Platform — backend entrypoint.

Run locally:      uvicorn app.main:app --reload --port 8080
Run on staging:    see src/backend/README.md (systemd unit / process manager
                    per BRD/PRD Section 18.7 — one process per project).

Until the API Gateway (BRD/PRD Section 18.6) is provisioned, this process
also serves the built frontend (../web/dist) directly, per the frontend
README's staging note -- so one process on one port serves both the API
and the wizard UI, with no CORS/reverse-proxy setup required on staging.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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


# --- Static frontend (apps/web/dist), mounted after the API routes above so
# /api/* is always matched first. Absent in local dev unless `npm run build`
# has been run; staging should build the frontend before starting this
# process (see apps/web/README.md).
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback: any non-API, non-asset path serves index.html so
        client-side routing (if added later) and hard refreshes both work."""
        if full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    logging.getLogger("phoneme.main").warning(
        "apps/web/dist not found -- frontend not mounted. Run `npm run build` "
        "in apps/web/ before starting this process to serve the UI too."
    )
