"""
Session store.

Postgres-backed (SQLAlchemy Core + asyncpg) when config.DATABASE_URL points
at Postgres -- staging/prod, per db/schema.sql's `wizard_sessions` table.
Falls back to the original in-process dict when it doesn't (local/dev
default, config.DATABASE_URL = sqlite:///./phoneme_sdlc.db), so
`uvicorn --reload` with zero setup still works unchanged -- this module is
the seam the old in-memory store's docstring pointed at.

Requirements are stored inside the same `wizard_sessions.state` JSONB
column as a sibling key next to the serialized SessionState, rather than a
new table/migration: db/schema.sql's `requirements` table is the
normalized *post-graduation* one (module_id FK, requirement_version rows,
etc.), a different shape from this pilot's per-session Requirement model,
and this wizard-stage data isn't ready to graduate into it yet (see
generate_brd_prd() in routers/wizard.py for where that graduation
happens).

Every write here is a read-modify-write of the one row for that
session_id -- fine for this pilot's traffic (one person iterating on one
session at a time); it is not safe under concurrent writers to the same
session_id without adding row locking, which is out of scope for the
durability fix this module exists for.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy import Column, DateTime, MetaData, Table, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.sql import insert, select, update

from . import config
from .models import Requirement, SessionState

logger = logging.getLogger("phoneme.store")

_metadata = MetaData()

wizard_sessions = Table(
    "wizard_sessions",
    _metadata,
    Column("session_id", UUID(as_uuid=False), primary_key=True),
    Column("state", JSONB, nullable=False),
    Column("product_id", UUID(as_uuid=False), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)


def _is_postgres(url: str) -> bool:
    return url.startswith("postgres")


def _async_url(url: str) -> str:
    """Normalize a plain postgres:// / postgresql:// URL (what the
    credentials file / .env hold) to the asyncpg driver URL SQLAlchemy
    needs (postgresql+asyncpg://)."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


_USE_DB = _is_postgres(config.DATABASE_URL)
_engine: Optional[AsyncEngine] = None

# --- in-memory fallback (unchanged pilot behavior) for local/dev sqlite ---
_sessions: dict[str, SessionState] = {}
_requirements: dict[str, dict[str, Requirement]] = {}


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(_async_url(config.DATABASE_URL), pool_pre_ping=True)
    return _engine


async def dispose_engine() -> None:
    """Call from a FastAPI shutdown handler so pooled connections aren't
    left open across a reload/restart."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def _envelope(state: SessionState, requirements: dict[str, Requirement]) -> dict:
    return {
        "session_state": state.model_dump(mode="json"),
        "requirements": {rid: r.model_dump(mode="json") for rid, r in requirements.items()},
    }


def _from_envelope(raw: dict) -> tuple[SessionState, dict[str, Requirement]]:
    state = SessionState.model_validate(raw["session_state"])
    reqs = {rid: Requirement.model_validate(r) for rid, r in raw.get("requirements", {}).items()}
    return state, reqs


async def _load_row(session_id: str) -> Optional[dict]:
    engine = get_engine()
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                select(wizard_sessions.c.state).where(wizard_sessions.c.session_id == session_id)
            )
        ).first()
    return None if row is None else row.state


async def new_session() -> SessionState:
    sid = str(uuid.uuid4())
    state = SessionState(session_id=sid)
    if not _USE_DB:
        _sessions[sid] = state
        _requirements[sid] = {}
        return state

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(insert(wizard_sessions).values(session_id=sid, state=_envelope(state, {})))
    return state


async def get_session(session_id: str) -> Optional[SessionState]:
    if not _USE_DB:
        return _sessions.get(session_id)

    raw = await _load_row(session_id)
    if raw is None:
        return None
    state, _ = _from_envelope(raw)
    return state


async def save_session(state: SessionState) -> None:
    if not _USE_DB:
        _sessions[state.session_id] = state
        return

    raw = await _load_row(state.session_id)
    _, reqs = _from_envelope(raw) if raw is not None else (None, {})

    engine = get_engine()
    async with engine.begin() as conn:
        values = dict(state=_envelope(state, reqs), updated_at=func.now())
        result = await conn.execute(
            update(wizard_sessions).where(wizard_sessions.c.session_id == state.session_id).values(**values)
        )
        if result.rowcount == 0:
            # Safety net for a session_id that was minted before the row
            # existed (shouldn't happen via new_session(), but don't lose
            # the caller's write if it does) rather than the expected path.
            await conn.execute(insert(wizard_sessions).values(session_id=state.session_id, **values))


async def add_requirement(session_id: str, req: Requirement) -> None:
    if not _USE_DB:
        _requirements.setdefault(session_id, {})[req.req_id] = req
        return

    raw = await _load_row(session_id)
    if raw is None:
        logger.warning("add_requirement called for unknown session_id=%s", session_id)
        return
    state, reqs = _from_envelope(raw)
    reqs[req.req_id] = req

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            update(wizard_sessions)
            .where(wizard_sessions.c.session_id == session_id)
            .values(state=_envelope(state, reqs), updated_at=func.now())
        )


async def list_requirements(session_id: str) -> list[Requirement]:
    if not _USE_DB:
        return list(_requirements.get(session_id, {}).values())

    raw = await _load_row(session_id)
    if raw is None:
        return []
    _, reqs = _from_envelope(raw)
    return list(reqs.values())


async def get_requirement(session_id: str, req_id: str) -> Optional[Requirement]:
    if not _USE_DB:
        return _requirements.get(session_id, {}).get(req_id)

    raw = await _load_row(session_id)
    if raw is None:
        return None
    _, reqs = _from_envelope(raw)
    return reqs.get(req_id)
