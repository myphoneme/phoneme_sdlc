"""
Shared review engine for the SDLC stages after the BRD/PRD (2026-10-04):
Technical Design and UI/UX.

Both follow exactly the same rules the BRD/PRD Manager established with the
product owner on the RelayReel dry run:
  * documents are drafted in the background with live progress,
  * every AI rewrite from a comment is a proposal (accept / discard),
  * open questions must be answered or explicitly deferred -- a document
    with open questions cannot be approved or frozen,
  * frozen documents are baselined as versions (v1.0, v1.1 ...) that
    become the Change Log of the exported document, and baselining opens
    the next stage.
Each stage plugs in a Kind with its own drafting function.
"""
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, HTTPException

from . import store
from .locks import session_lock
from .models import (
    Baseline, Decision, GenerationItem, GenerationProgress, ItemAnswersRequest,
    ItemCommentRequest, ItemRequest, ReviewMessage, SessionState,
)

logger = logging.getLogger("phoneme.review")
STALE_AFTER_S = 600
_tasks: set[asyncio.Task] = set()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(q: str) -> str:
    return " ".join((q or "").lower().split()).rstrip("?. ")


@dataclass
class Kind:
    doc_type: str                  # techdesign | uiux (also the URL prefix)
    label: str                     # human name, e.g. "Technical Design"
    list_attr: str                 # SessionState attribute holding the items
    id_attr: str                   # item id attribute
    gen_attr: str                  # SessionState GenerationProgress attribute
    stage: str                     # the wizard stage this kind lives in
    next_stage: str                # stage opened by a baseline
    plan: Callable[[SessionState], Awaitable[list]]              # -> new items to draft
    draft: Callable[[SessionState, Any, Optional[str]], Awaitable[Any]]  # -> doc
    record_deferred: Callable[[Any, str], None]                  # doc, text
    ready: Callable[[SessionState], Optional[str]] = lambda s: None  # error if not ready
    merge: Callable[[Any, Any], Any] = lambda old, new: new  # keep user content (e.g. uploads) when a draft lands
    on_baseline: Optional[Callable[[SessionState], Awaitable[Any]]] = None  # file the documents


def items(kind: Kind, state: SessionState) -> list:
    return getattr(state, kind.list_attr)


def find(kind: Kind, state: SessionState, item_id: str):
    it = next((x for x in items(kind, state) if getattr(x, kind.id_attr) == item_id), None)
    if not it:
        raise HTTPException(404, f"{kind.label} document not found")
    return it


def doc_hash(item) -> str:
    raw = json.dumps(item.doc.model_dump() if item.doc else None, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def baseline_status(kind: Kind, state: SessionState) -> dict:
    its = items(kind, state)
    prev = [b for b in state.baselines if b.doc_type == kind.doc_type]
    last = prev[-1] if prev else None
    cur = {getattr(i, kind.id_attr): doc_hash(i) for i in its}
    changed = [] if not last else sorted(k for k in set(cur) | set(last.snapshot) if cur.get(k) != last.snapshot.get(k))
    if last:
        major, minor = last.version.split(".")
        nxt = f"{major}.{int(minor) + 1}"
    else:
        nxt = "1.0"
    return {
        "all_frozen": bool(its) and all(i.status == "Frozen" for i in its),
        "version": last.version if last else None,
        "changed_since": changed,
        "next_version": nxt,
    }


async def _session(session_id: str) -> SessionState:
    state = await store.get_session(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    return state


def _stale(g: GenerationProgress) -> bool:
    if not g.updated_at:
        return True
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(g.updated_at)).total_seconds() > STALE_AFTER_S
    except ValueError:
        return True


async def _run(kind: Kind, session_id: str) -> None:
    state = await store.get_session(session_id)
    if not state:
        return
    g: GenerationProgress = getattr(state, kind.gen_attr)
    for gi in g.items:
        if gi.status == "done":
            continue
        gi.status = "drafting"
        g.updated_at = now()
        await store.save_session(state)
        try:
            item = find(kind, state, gi.req_id)
            doc = await kind.draft(state, item, None)
            state = await store.get_session(session_id) or state
            g = getattr(state, kind.gen_attr)
            gi = next(x for x in g.items if x.req_id == gi.req_id)
            item = find(kind, state, gi.req_id)
            item.doc = kind.merge(item.doc, doc)
            item.status = "Draft"
            gi.status = "done"
            g.done = sum(1 for x in g.items if x.status == "done")
        except Exception as exc:  # noqa: BLE001
            logger.exception("%s drafting failed for %s", kind.label, gi.module)
            gi.status, gi.error = "failed", f"{type(exc).__name__}: {str(exc)[:200]}"
        g.updated_at = now()
        await store.save_session(state)
    g.status = "failed" if any(x.status == "failed" for x in g.items) else "done"
    g.updated_at = now()
    await store.save_session(state)


def make_router(kind: Kind) -> APIRouter:
    r = APIRouter(prefix=f"/api/{kind.doc_type}", tags=[kind.doc_type])

    @r.post("/{session_id}/generate", response_model=SessionState)
    async def generate(session_id: str):
        async with session_lock(session_id, f"{kind.doc_type}-generate"):
            state = await _session(session_id)
            err = kind.ready(state)
            if err:
                raise HTTPException(409, err)
            g: GenerationProgress = getattr(state, kind.gen_attr)
            if g.status == "running" and not _stale(g):
                return state
            for it in await kind.plan(state):
                items(kind, state).append(it)
            its = items(kind, state)
            gi = [GenerationItem(module=i.module, req_id=getattr(i, kind.id_attr),
                                 status="done" if i.doc else "queued") for i in its]
            if all(x.status == "done" for x in gi):
                g.status = "done"
                await store.save_session(state)
                return state
            setattr(state, kind.gen_attr, GenerationProgress(
                status="running", total=len(gi), done=sum(1 for x in gi if x.status == "done"),
                items=gi, started_at=now(), updated_at=now(),
            ))
            await store.save_session(state)
            t = asyncio.create_task(_run(kind, session_id))
            _tasks.add(t)
            t.add_done_callback(_tasks.discard)
            return state

    @r.post("/{session_id}/comment", response_model=SessionState)
    async def comment(session_id: str, req: ItemCommentRequest):
        async with session_lock(session_id, f"{kind.doc_type}:{req.item_id}"):
            state = await _session(session_id)
            it = find(kind, state, req.item_id)
            if it.status == "Frozen":
                raise HTTPException(409, "unfreeze the document to change it")
            if not it.doc:
                raise HTTPException(409, "this document has not been drafted yet")
            doc = await kind.draft(state, it, f"Reviewer comment: {req.comment}\n\nRevise the document to address the comment. Keep everything that is still correct.")
            state = await _session(session_id)
            it = find(kind, state, req.item_id)
            it.thread.append(ReviewMessage(role="owner", text=req.comment, at=now()))
            it.revised_doc = doc
            if not it.status.startswith("Revised"):
                it.status_before_revision = it.status
            it.status = "Revised — needs re-review"
            it.thread.append(ReviewMessage(role="assistant", at=now(), text="I've drafted a revision for your comment — review it and accept or discard it."))
            await store.save_session(state)
            return state

    @r.post("/{session_id}/accept", response_model=SessionState)
    async def accept(session_id: str, req: ItemRequest):
        state = await _session(session_id)
        it = find(kind, state, req.item_id)
        if it.revised_doc is not None:
            it.doc, it.revised_doc = it.revised_doc, None
            it.status_before_revision = None
            it.status = "Draft" if it.doc.open_questions else "Approved"
        else:
            if not it.doc:
                raise HTTPException(409, "this document has not been drafted yet")
            n = len(it.doc.open_questions)
            if n:
                raise HTTPException(409, f"answer or defer the {n} open question{'s' if n > 1 else ''} before approving")
            it.status = "Approved"
        await store.save_session(state)
        return state

    @r.post("/{session_id}/discard", response_model=SessionState)
    async def discard(session_id: str, req: ItemRequest):
        state = await _session(session_id)
        it = find(kind, state, req.item_id)
        it.revised_doc = None
        it.status = it.status_before_revision or "Draft"
        it.status_before_revision = None
        await store.save_session(state)
        return state

    @r.post("/{session_id}/answers", response_model=SessionState)
    async def answers(session_id: str, req: ItemAnswersRequest):
        async with session_lock(session_id, f"{kind.doc_type}:{req.item_id}"):
            state = await _session(session_id)
            it = find(kind, state, req.item_id)
            if not it.doc:
                raise HTTPException(409, "this document has not been drafted yet")
            if it.revised_doc is not None:
                raise HTTPException(409, "accept or discard the pending revision first")
            if it.status == "Frozen":
                raise HTTPException(409, "unfreeze the document to change it")
            got = [a for a in req.answers if a.question.strip() and (a.defer or a.answer.strip())]
            if not got:
                raise HTTPException(400, "answer or defer at least one question")
            lines = [f"Q: {a.question}\n" + (("DEFERRED to a later release" + (f" -- {a.answer.strip()}" if a.answer.strip() else "")) if a.defer else f"A: {a.answer.strip()}") for a in got]
            before = {norm(q) for q in it.doc.open_questions}
            doc = await kind.draft(state, it, (
                "The product owner has answered open questions:\n\n" + "\n\n".join(lines) + "\n\n"
                "Revise the document: apply each answer where it belongs as a firm decision. Remove "
                "every answered or deferred question from open_questions and keep the others. Add a "
                "NEW open question only if an answer creates a real decision still to be made (at most 2). "
                "Keep everything else that is still correct."
            ))
            closed = {norm(a.question) for a in got}
            doc.open_questions = [q for q in doc.open_questions if norm(q) not in closed]
            for a in got:
                if a.defer:
                    kind.record_deferred(doc, a.question.strip().rstrip("?") + (f" ({a.answer.strip()})" if a.answer.strip() else ""))
            state = await _session(session_id)
            it = find(kind, state, req.item_id)
            it.doc = doc
            ts = now()
            for a in got:
                it.decisions.append(Decision(question=a.question.strip(), answer=a.answer.strip(), deferred=a.defer, at=ts))
            it.thread.append(ReviewMessage(role="owner", at=ts, text="\n\n".join(lines)))
            new_qs = [q for q in doc.open_questions if norm(q) not in before]
            left = len(doc.open_questions)
            n_ans = sum(1 for a in got if not a.defer)
            msg = f"Updated the document with {n_ans} answer{'s' if n_ans != 1 else ''}"
            n_def = len(got) - n_ans
            if n_def:
                msg += f" and {n_def} deferred question{'s' if n_def != 1 else ''}"
            msg += "."
            if new_qs:
                msg += f" Your answers raised {len(new_qs)} follow-up question{'s' if len(new_qs) != 1 else ''}: " + " ".join(new_qs)
            elif left:
                msg += f" {left} open question{'s' if left != 1 else ''} still need an answer."
            else:
                msg += " No open questions remain — review the document and approve it."
            it.thread.append(ReviewMessage(role="assistant", at=ts, text=msg))
            if it.status == "Approved" and left:
                it.status = "Draft"
            await store.save_session(state)
            return state

    @r.post("/{session_id}/freeze/{item_id}", response_model=SessionState)
    async def freeze(session_id: str, item_id: str):
        state = await _session(session_id)
        it = find(kind, state, item_id)
        if it.revised_doc is not None:
            raise HTTPException(409, "accept or discard the pending revision before freezing")
        if not it.doc:
            raise HTTPException(409, "this document has not been drafted yet")
        if it.doc.open_questions:
            raise HTTPException(409, "answer or defer every open question before freezing")
        if it.status != "Approved":
            raise HTTPException(409, "approve the document before freezing it")
        it.status = "Frozen"
        await store.save_session(state)
        return state

    @r.post("/{session_id}/unfreeze/{item_id}", response_model=SessionState)
    async def unfreeze(session_id: str, item_id: str):
        state = await _session(session_id)
        it = find(kind, state, item_id)
        if it.status == "Frozen":
            it.status = "Approved"
            await store.save_session(state)
        return state

    @r.get("/{session_id}/baseline")
    async def get_baseline(session_id: str):
        return baseline_status(kind, await _session(session_id))

    @r.post("/{session_id}/baseline", response_model=SessionState)
    async def create_baseline(session_id: str):
        async with session_lock(session_id, f"{kind.doc_type}-baseline"):
            state = await _session(session_id)
            st = baseline_status(kind, state)
            if not st["all_frozen"]:
                raise HTTPException(409, f"freeze every {kind.label} document before baselining")
            if st["version"] and not st["changed_since"]:
                return state
            its = items(kind, state)
            if st["version"]:
                desc = "Revised after re-review: " + ", ".join(st["changed_since"])
            else:
                n_dec = sum(len(i.decisions) for i in its)
                desc = f"Initial baseline — {len(its)} documents frozen" + (f", {n_dec} product-owner decisions recorded" if n_dec else "")
            state.baselines.append(Baseline(
                doc_type=kind.doc_type, version=st["next_version"], at=now(), description=desc,
                snapshot={getattr(i, kind.id_attr): doc_hash(i) for i in its},
            ))
            if state.stage == kind.stage:
                state.stage = kind.next_stage
            await store.save_session(state)
            if kind.on_baseline:
                await kind.on_baseline(state)
            return state

    return r
