"""
Stage 4 — BRD/PRD Manager: list requirements, comment, regenerate-from-
comments, accept/discard, freeze -- plus restructure (2026-09-30) to turn a
legacy prose requirement into the structured, business-language format.

Every AI rewrite is a *proposal* (revised_doc/revised_body): the reviewer
sees it next to the current version and accepts or discards it.
"""
import json

from fastapi import APIRouter, HTTPException

from datetime import datetime, timezone

from .. import ai_router, reqdoc, store
from ..locks import session_lock
from ..models import (
    AcceptRequest, CommentRequest, ConsistencyIssue, ConsistencyReport,
    Requirement, SessionState,
)

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
    if not r.doc:
        raise HTTPException(400, "restructure this requirement into the readable format before freezing it")
    r.status = "Frozen"
    await store.add_requirement(session_id, r)
    return r


@router.post("/{session_id}/unfreeze/{req_id}", response_model=Requirement)
async def unfreeze_requirement(session_id: str, req_id: str):
    """Reopen a frozen requirement for changes (it goes back to Approved)."""
    r = await store.get_requirement(session_id, req_id)
    if not r:
        raise HTTPException(404, "requirement not found")
    if r.status != "Frozen":
        return r
    r.status = "Approved"
    await store.add_requirement(session_id, r)
    return r


def _doc_digest(r: Requirement) -> str:
    if r.doc:
        steps = "; ".join(f"{i}. {j.title}" for i, j in enumerate(r.doc.journey, 1))
        return f"[{r.req_id}] {r.title} (module: {r.module})\nSummary: {r.doc.summary}\nSteps: {steps}"
    return f"[{r.req_id}] {r.title} (module: {r.module})\n{r.body[:1200]}"


@router.post("/{session_id}/consistency", response_model=SessionState)
async def check_consistency(session_id: str):
    """Cross-document check (2026-09-30 RelayReel review: RELA-002 and
    RELA-003 retold the same journey and nothing flagged it). Looks across
    the whole set for overlapping scope, contradictions and gaps."""
    async with session_lock(session_id, "consistency"):
        state = await store.get_session(session_id)
        if not state:
            raise HTTPException(404, "session not found")
        reqs = sorted(await store.list_requirements(session_id), key=lambda r: r.req_id)
        if len(reqs) < 2:
            raise HTTPException(400, "need at least two requirements to compare")
        result = await ai_router.generate(
            ai_router.Feature.BRD_PRD_DRAFTING,
            f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n\n"
            "Requirement documents:\n\n" + "\n\n".join(_doc_digest(r) for r in reqs) + "\n\n"
            "Review these as ONE set. Find (a) overlap: two documents describing "
            "the same steps or capability, (b) contradictions, (c) gaps: an "
            "obvious hand-off nobody owns. Ignore wording differences. Respond "
            'with ONLY JSON: {"verdict": "one sentence overall", "issues": '
            '[{"documents": ["<req ids>"], "problem": "<one plain sentence>", '
            '"suggestion": "<one plain sentence: what to change, in which document>"}]}. '
            "Return an empty issues list if the set is clean. Max 8 issues, most important first.",
            system="You are a lead business analyst reviewing a BRD/PRD for overlap and consistency. JSON only.",
        )
        try:
            data = reqdoc._extract_json(result["text"])
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(502, "the AI did not return a usable review — try again")
        ids = {r.req_id for r in reqs}
        issues = []
        for it in data.get("issues", [])[:8]:
            if not isinstance(it, dict):
                continue
            docs = [d for d in (it.get("documents") or []) if d in ids]
            prob = reqdoc._clean(it.get("problem"))
            if prob:
                issues.append(ConsistencyIssue(documents=docs, problem=prob, suggestion=reqdoc._clean(it.get("suggestion"))))
        state.consistency = ConsistencyReport(
            checked_at=datetime.now(timezone.utc).isoformat(),
            verdict=reqdoc._clean(data.get("verdict")), issues=issues,
        )
        await store.save_session(state)
        return state
