"""
Stage 4 — BRD/PRD Manager: list requirements, comment, regenerate-from-
comments, accept/discard. Ports the mock's diff -> Accept & commit /
Discard flow onto the real AI router.
"""
from fastapi import APIRouter, HTTPException

from .. import ai_router, store
from ..models import CommentRequest, AcceptRequest, Requirement

router = APIRouter(prefix="/api/brdprd", tags=["brdprd"])


@router.get("/{session_id}/requirements", response_model=list[Requirement])
async def list_requirements(session_id: str):
    if not store.get_session(session_id):
        raise HTTPException(404, "session not found")
    return store.list_requirements(session_id)


@router.post("/{session_id}/comment", response_model=Requirement)
async def comment_and_regenerate(session_id: str, req: CommentRequest):
    """Regenerate-from-comments — critical tier: rewrites an already-drafted requirement."""
    state = store.get_session(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    r = store.get_requirement(session_id, req.req_id)
    if not r:
        raise HTTPException(404, "requirement not found")

    result = await ai_router.generate(
        ai_router.Feature.REGENERATE_FROM_COMMENTS,
        f"Current requirement ({r.title}):\n{r.body}\n\n"
        f"Reviewer comment: {req.comment}\n\n"
        "Rewrite the requirement body to address the comment. Return only "
        "the revised body text.",
        system="You are the BRD/PRD Manager's regenerate-from-comments step.",
    )
    r.revised_body = result["text"].strip()
    r.status = "Revised — needs re-review"
    store.add_requirement(session_id, r)
    return r


@router.post("/{session_id}/accept", response_model=Requirement)
async def accept_revision(session_id: str, req: AcceptRequest):
    r = store.get_requirement(session_id, req.req_id)
    if not r:
        raise HTTPException(404, "requirement not found")
    if r.revised_body:
        r.body = r.revised_body
        r.revised_body = None
    r.status = "Approved"
    store.add_requirement(session_id, r)
    return r


@router.post("/{session_id}/discard", response_model=Requirement)
async def discard_revision(session_id: str, req: AcceptRequest):
    r = store.get_requirement(session_id, req.req_id)
    if not r:
        raise HTTPException(404, "requirement not found")
    r.revised_body = None
    r.status = "Draft"
    store.add_requirement(session_id, r)
    return r


@router.post("/{session_id}/freeze/{req_id}", response_model=Requirement)
async def freeze_requirement(session_id: str, req_id: str):
    r = store.get_requirement(session_id, req_id)
    if not r:
        raise HTTPException(404, "requirement not found")
    r.status = "Frozen"
    store.add_requirement(session_id, r)
    return r
