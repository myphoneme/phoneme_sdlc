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
from datetime import datetime, timezone
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
# created_at/updated_at for the in-memory path -- the dict above has no
# timestamp columns the way wizard_sessions does, but list_sessions() (added
# for the dashboard) needs both to sort by recency and show "Started X ago",
# so track them alongside it here.
_meta: dict[str, dict] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        now = _now_iso()
        _meta[sid] = {"created_at": now, "updated_at": now}
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
        now = _now_iso()
        _meta.setdefault(state.session_id, {"created_at": now}).update(updated_at=now)
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


async def clear_requirements(session_id: str) -> list[Requirement]:
    """Remove and return every requirement for a session (used when scope is
    redefined -- the caller archives them on the SessionState so nothing is
    lost)."""
    if not _USE_DB:
        return list(_requirements.pop(session_id, {}).values())

    raw = await _load_row(session_id)
    if raw is None:
        return []
    state, reqs = _from_envelope(raw)
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            update(wizard_sessions)
            .where(wizard_sessions.c.session_id == session_id)
            .values(state=_envelope(state, {}), updated_at=func.now())
        )
    return list(reqs.values())


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


def _display_name(state: SessionState) -> str:
    """The dashboard card's title for a session that may not have a
    selected_name yet -- falls back to a short prefix of the concept
    summary, then to a plain placeholder, rather than showing a bare id."""
    if state.selected_name:
        return state.selected_name
    if state.concept_summary:
        summary = state.concept_summary.strip()
        return (summary[:60] + "…") if len(summary) > 60 else summary
    return "Untitled idea"


async def list_sessions() -> list[dict]:
    """Summary rows for the dashboard's product grid -- session_id, a
    display name, the real stage, and both timestamps, newest-updated
    first. Deliberately not the full SessionState (messages/research/etc.)
    since the dashboard only needs enough to render a card; the wizard view
    fetches the full state itself via get_session() once a card is opened."""
    if not _USE_DB:
        rows = [
            {
                "session_id": sid,
                "name": _display_name(state),
                "stage": state.stage,
                "created_at": _meta.get(sid, {}).get("created_at"),
                "updated_at": _meta.get(sid, {}).get("updated_at") or _meta.get(sid, {}).get("created_at"),
            }
            for sid, state in _sessions.items()
        ]
        rows.sort(key=lambda r: r["updated_at"] or "", reverse=True)
        return rows

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            select(
                wizard_sessions.c.session_id,
                wizard_sessions.c.state,
                wizard_sessions.c.created_at,
                wizard_sessions.c.updated_at,
            ).order_by(wizard_sessions.c.updated_at.desc())
        )
        db_rows = result.all()

    rows = []
    for row in db_rows:
        state, _ = _from_envelope(row.state)
        rows.append(
            {
                "session_id": row.session_id,
                "name": _display_name(state),
                "stage": state.stage,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )
    return rows
