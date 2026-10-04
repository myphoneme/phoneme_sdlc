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
    AcceptRequest, AnswersRequest, CommentRequest, ConsistencyIssue, ConsistencyReport,
    Decision, Requirement, ReviewMessage, SessionState,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(q: str) -> str:
    return " ".join((q or "").lower().split()).rstrip("?. ")


def _open_questions(r: Requirement) -> list[str]:
    return list(r.doc.open_questions) if r.doc else []

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
        r.thread.append(ReviewMessage(role="owner", text=req.comment, at=_now()))
        r = await _propose(
            session_id, r,
            f"Reviewer comment: {req.comment}\n\nRewrite the requirement to address "
            "the comment. Keep everything that is still correct.",
        )
        r.thread.append(ReviewMessage(role="assistant", at=_now(), text=(
            "I've drafted a revision for your comment — review it above and accept or discard it."
        )))
        await store.add_requirement(session_id, r)
        return r


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
    revising = bool(r.revised_body or r.revised_doc)
    if not revising and r.doc and r.doc.open_questions:
        n = len(r.doc.open_questions)
        raise HTTPException(409, f"answer or defer the {n} open question{'s' if n > 1 else ''} before approving")
    if revising:
        r.body = r.revised_body or r.body
        r.doc = r.revised_doc or r.doc
        r.title = r.revised_title or r.title
    r.revised_body = None
    r.revised_doc = None
    r.revised_title = None
    r.status_before_revision = None
    # Accepting a revision that still has open questions keeps it in Draft.
    r.status = "Draft" if _open_questions(r) else "Approved"
    await store.add_requirement(session_id, r)
    return r


@router.post("/{session_id}/answers", response_model=Requirement)
async def answer_open_questions(session_id: str, req: AnswersRequest):
    """The product owner answers (or defers) open questions; the document
    is revised straight away with those decisions. If an answer raises a
    genuine new decision, it comes back as a follow-up question, so review
    continues as a conversation until nothing is open."""
    async with session_lock(session_id, f"req:{req.req_id}"):
        state = await store.get_session(session_id)
        r = await store.get_requirement(session_id, req.req_id)
        if not state or not r:
            raise HTTPException(404, "requirement not found")
        if not r.doc:
            raise HTTPException(400, "restructure this requirement first")
        if r.revised_doc or r.revised_body:
            raise HTTPException(409, "accept or discard the pending revision first")
        if r.status == "Frozen":
            raise HTTPException(409, "unfreeze the document to change it")
        items = [a for a in req.answers if a.question.strip() and (a.defer or a.answer.strip())]
        if not items:
            raise HTTPException(400, "answer or defer at least one question")
        answered = [a for a in items if not a.defer]
        deferred = [a for a in items if a.defer]
        lines = []
        for a in answered:
            lines.append(f"Q: {a.question}\nA: {a.answer.strip()}")
        for a in deferred:
            lines.append(f"Q: {a.question}\nDEFERRED to a later release" + (f" -- {a.answer.strip()}" if a.answer.strip() else ""))
        title, doc = await reqdoc.generate_doc(
            f"Product: {state.selected_name}\nConcept: {state.concept_summary}\nModule: {r.module}\n\n"
            f"Current requirement:\n{_current_as_text(r)}\n\n"
            "The product owner has answered open questions:\n\n" + "\n\n".join(lines) + "\n\n"
            "Revise the requirement: write each answer into the section where it belongs "
            "(journey steps, business rules, acceptance criteria) as a firm decision. Remove "
            "every answered or deferred question from open_questions. Record each deferred "
            "question in out_of_scope as 'Deferred to a later release: <topic>'. Keep every "
            "other open question unchanged. Add a NEW open question only if an answer "
            "creates a real decision the owner still has to make (at most 2). Keep "
            "everything else that is still correct.",
            fallback_title=r.title,
        )
        # Enforce the decisions even if the model forgets one.
        closed = {_norm(a.question) for a in items}
        doc.open_questions = [q for q in doc.open_questions if _norm(q) not in closed]
        for a in deferred:
            topic = a.question.strip().rstrip("?")
            if not any(_norm(topic)[:40] in _norm(x) for x in doc.out_of_scope):
                doc.out_of_scope.append(f"Deferred to a later release: {topic}" + (f" ({a.answer.strip()})" if a.answer.strip() else ""))
        before = set(_norm(q) for q in _open_questions(r))
        new_qs = [q for q in doc.open_questions if _norm(q) not in before]
        r.title, r.doc, r.body = title or r.title, doc, reqdoc.render_text(title or r.title, doc)
        now = _now()
        for a in items:
            r.decisions.append(Decision(question=a.question.strip(), answer=a.answer.strip(), deferred=a.defer, at=now))
        r.thread.append(ReviewMessage(role="owner", at=now, text="\n\n".join(lines)))
        left = len(doc.open_questions)
        msg = f"Updated the document with {len(answered)} answer{'s' if len(answered) != 1 else ''}"
        if deferred:
            msg += f" and {len(deferred)} deferred question{'s' if len(deferred) != 1 else ''} (listed under Out of scope)"
        msg += "."
        if new_qs:
            msg += f" Your answers raised {len(new_qs)} follow-up question{'s' if len(new_qs) != 1 else ''}: " + " ".join(new_qs)
        elif left:
            msg += f" {left} open question{'s' if left != 1 else ''} still need an answer."
        else:
            msg += " No open questions remain — review the document and approve it."
        r.thread.append(ReviewMessage(role="assistant", at=now, text=msg))
        if r.status == "Approved" and left:
            r.status = "Draft"
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
    if r.doc.open_questions:
        raise HTTPException(409, "answer or defer every open question before freezing")
    if r.status != "Approved":
        raise HTTPException(409, "approve the document before freezing it")
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
