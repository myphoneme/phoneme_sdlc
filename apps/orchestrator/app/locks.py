"""
Per-session operation locks.

2026-09-30 dry-run finding: with the same idea open in two browser tabs,
each tab independently fired the (paid, web-search-grounded) research call
because the frontend auto-starts it on mount. Every expensive, idempotent
step now runs under a (session_id, operation) lock: the second caller waits
for the first to finish, re-reads the session, sees the work is already
done, and returns it instead of paying for it twice.

In-process only -- correct for the single uvicorn process staging runs
today (BRD/PRD Section 18.7). Multiple workers would need a DB advisory
lock instead.
"""
import asyncio
from collections import defaultdict

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def session_lock(session_id: str, op: str) -> asyncio.Lock:
    return _locks[f"{session_id}:{op}"]
