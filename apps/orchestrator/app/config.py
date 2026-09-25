"""
Phoneme SDLC Platform — backend configuration.

All values are overridable via environment variables so the same code runs
unchanged across dev / staging without editing source (BRD/PRD Section
18.7 — per-project .env for runtime config; secrets belong in the
Security service's secrets store, never committed here).
"""
import os

# --- AI routing (BRD/PRD Section 18.8 / TDD Section 8 — reviewed decision) ---
OLLAMA_URL = os.environ.get("AI_GATEWAY_URL", "http://10.100.60.121:8000/v1/chat/completions")
OLLAMA_MODEL = os.environ.get("AI_GATEWAY_MODEL", "gemma4:e4b")
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("AI_GATEWAY_TIMEOUT", "60"))

# Commercial tier — provider selected per COMMERCIAL_PROVIDER. Each provider's
# API key comes from the Security service's secrets store on staging; here it
# is read from the environment only as a local/dev convenience.
COMMERCIAL_PROVIDER = os.environ.get("COMMERCIAL_PROVIDER", "anthropic")  # anthropic | gemini | astra
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
# "Astra" — provider unconfirmed (BRD/PRD Section 18.8 footnote / TDD Section 9
# open item). Wired as a placeholder slot so the router doesn't need changes
# once the provider is confirmed.
ASTRA_API_KEY = os.environ.get("ASTRA_API_KEY", "")
ASTRA_API_URL = os.environ.get("ASTRA_API_URL", "")

# --- Storage ---
# Pilot/dev default: SQLite file, zero external dependency. Staging should
# set DATABASE_URL to the project's dedicated Postgres database on the DB
# Server (BRD/PRD Section 18.7) once the SQLAlchemy models are pointed at it.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./phoneme_sdlc.db")

# --- CORS (React-Vite dev server / staging frontend origin) ---
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
