"""
Stage 4 — BRD/PRD Manager: list requirements, comment, regenerate-from-
comments, accept/discard, freeze -- plus restructure (2026-09-30) to turn a
legacy prose requirement into the structured, business-language format.

Every AI rewrite is a *proposal* (revised_doc/revised_body): the reviewer
sees it next to the current version and accepts or discards it.
"""
import json

from fastapi import APIRouter, HTTPException

from .. import reqdoc, store
from ..locks import session_lock
from ..models import AcceptRequest, CommentRequest, Requirement

router = APIRouter(prefix="/api/brdprd", tags=["brdprd"])


@router.get("/{session_id}/requirements", response_model=list[Requirement])
async def list_requirements(session_id: str):
    if not await store.get_session(session_id):
        raise HTTPException(404, "session not found")
    reqs = await store.list_requirements(session_id)
    return sorted(reqs, key=lambda r: r.req_id)


def _current_as_text(r: Requirement) -> str:
    if r.doc:
        return json.dumps({"title": r.title, **r.doc.model_dump()}, ensure_ascii=False)
    return f"{r.title}\n{r.body}"


async def _propose(session_id: str, r: Requirement, instruction: str) -> Requirement:
    state = await store.get_session(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    title, doc = await reqdoc.generate_doc(
        f"Product: {state.selected_name}\nConcept: {state.concept_summary}\nModule: {r.module}\n\n"
        f"Current requirement:\n{_current_as_text(r)}\n\n{instruction}",
        fallback_title=r.title,
    )
    r.revised_title = title
    r.revised_doc = doc
    r.revised_body = reqdoc.render_text(title, doc)
    if not r.status.startswith("Revised"):
        r.status_before_revision = r.status
    r.status = "Revised — needs re-review"
    await store.add_requirement(session_id, r)
    return r


@router.post("/{session_id}/comment", response_model=Requirement)
async def comment_and_regenerate(session_id: str, req: CommentRequest):
    """Regenerate-from-comments — critical tier: proposes a rewrite."""
    async with session_lock(session_id, f"req:{req.req_id}"):
        r = await store.get_requirement(session_id, req.req_id)
        if not r:
            raise HTTPException(404, "requirement not found")
        return await _propose(
            session_id, r,
            f"Reviewer comment: {req.comment}\n\nRewrite the requirement to address "
            "the comment. Keep everything that is still correct.",
        )


@router.post("/{session_id}/restructure/{req_id}", response_model=Requirement)
async def restructure(session_id: str, req_id: str):
    """Convert a legacy prose requirement into the structured format
    (summary, journey, rules, acceptance criteria), stripping implementation
    detail. Proposed as a revision so the reviewer confirms nothing was
    lost."""
    async with session_lock(session_id, f"req:{req_id}"):
        r = await store.get_requirement(session_id, req_id)
        if not r:
            raise HTTPException(404, "requirement not found")
        if r.doc and not r.revised_doc:
            return r
        return await _propose(
            session_id, r,
            "Restructure this requirement into the format below WITHOUT "
            "changing its meaning or dropping any capability. Move every "
            "technical detail (endpoints, tables, queues, status codes) out "
            "-- express the same behaviour in business language.",
        )


@router.post("/{session_id}/accept", response_model=Requirement)
async def accept_revision(session_id: str, req: AcceptRequest):
    r = await store.get_requirement(session_id, req.req_id)
    if not r:
        raise HTTPException(404, "requirement not found")
    if r.revised_body or r.revised_doc:
        r.body = r.revised_body or r.body
        r.doc = r.revised_doc or r.doc
        r.title = r.revised_title or r.title
    r.revised_body = None
    r.revised_doc = None
    r.revised_title = None
    r.status_before_revision = None
    r.status = "Approved"
    await store.add_requirement(session_id, r)
    return r


@router.post("/{session_id}/discard", response_model=Requirement)
async def discard_revision(session_id: str, req: AcceptRequest):
    r = await store.get_requirement(session_id, req.req_id)
    if not r:
        raise HTTPException(404, "requirement not found")
    r.revised_body = None
    r.revised_doc = None
    r.revised_title = None
    r.status = r.status_before_revision or "Draft"
    r.status_before_revision = None
    await store.add_requirement(session_id, r)
    return r


@router.post("/{session_id}/freeze/{req_id}", response_model=Requirement)
async def freeze_requirement(session_id: str, req_id: str):
    r = await store.get_requirement(session_id, req_id)
    if not r:
        raise HTTPException(404, "requirement not found")
    if r.revised_body or r.revised_doc:
        raise HTTPException(400, "accept or discard the pending revision before freezing")
    r.status = "Frozen"
    await store.add_requirement(session_id, r)
    return r
