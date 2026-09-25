"""
In-process store for the pilot.

Deliberately a plain dict, not a database: it lets the whole wizard flow run
and be demoed with zero external dependency. Swap this module for a
SQLAlchemy-backed store pointed at the project's Postgres database (see
config.DATABASE_URL and BRD/PRD Section 18.7) before this leaves the pilot —
every function here is the seam to replace; callers only use these
functions, never the dict directly.
"""
import uuid
from typing import Optional

from .models import SessionState, Requirement

_sessions: dict[str, SessionState] = {}
_requirements: dict[str, dict[str, Requirement]] = {}  # session_id -> req_id -> Requirement


def new_session() -> SessionState:
    sid = str(uuid.uuid4())
    state = SessionState(session_id=sid)
    _sessions[sid] = state
    _requirements[sid] = {}
    return state


def get_session(session_id: str) -> Optional[SessionState]:
    return _sessions.get(session_id)


def save_session(state: SessionState) -> None:
    _sessions[state.session_id] = state


def add_requirement(session_id: str, req: Requirement) -> None:
    _requirements.setdefault(session_id, {})[req.req_id] = req


def list_requirements(session_id: str) -> list[Requirement]:
    return list(_requirements.get(session_id, {}).values())


def get_requirement(session_id: str, req_id: str) -> Optional[Requirement]:
    return _requirements.get(session_id, {}).get(req_id)
