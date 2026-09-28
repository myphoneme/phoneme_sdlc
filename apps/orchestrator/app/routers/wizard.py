"""
Stage 2 tail (Freeze Summary / Module Breakdown) and Stage 3 (Generating
BRD/PRD) endpoints.
"""
import re

from fastapi import APIRouter, HTTPException

from .. import ai_router, store
from ..models import (
    FlowCommentRequest,
    FlowFreezeRequest,
    FlowModuleRequest,
    FreezeRequest,
    GenerateRequest,
    ModuleFlow,
    Requirement,
    SessionState,
)

router = APIRouter(prefix="/api/wizard", tags=["wizard"])


def _strip_markdown(text: str) -> str:
    """Strip markdown bold/italic emphasis the model adds despite plain-text
    instructions -- same artifact class found in discovery-chat/research
    (see routers/discovery.py::_clean_line). Verified needed here too: the
    real model wraps requirement titles/bodies in **bold** (e.g. actor
    names, "**Title:**" prefixes) even when the system prompt doesn't yet
    forbid it."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)
    return text.strip()


def _research_context(state: SessionState) -> str:
    """Curated research-grounding text reused everywhere a prompt needs to
    stay anchored in the concept's actual research findings rather than
    inventing scope -- module breakdown, flow design, and (soon) BRD/PRD
    drafting all pull from the same block so they stay consistent with
    each other."""
    if not (state.research and state.research.recommended_features):
        return ""
    ctx = (
        "\n\nCompetitive research already surfaced these recommended "
        "features -- ground this in them rather than inventing scope from "
        "scratch:\n- " + "\n- ".join(state.research.recommended_features)
    )
    if state.research.risks:
        ctx += (
            "\n\nAlso known constraints/risks to stay realistic about:\n- "
            + "\n- ".join(state.research.risks)
        )
    if state.research.killer_feature:
        ctx += (
            "\n\nThe research identified this as the product's central "
            "differentiator -- make sure it has an obvious home, not buried "
            "as an afterthought: " + state.research.killer_feature
        )
    if state.research.positioning_reframe:
        ctx += "\n\nPositioning to keep in mind: " + state.research.positioning_reframe
    return ctx


@router.post("/freeze", response_model=SessionState)
async def freeze_scope(req: FreezeRequest):
    """Module-breakdown drafting that freezes scope — critical tier."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")

    research_context = _research_context(state)

    result = await ai_router.generate(
        ai_router.Feature.MODULE_BREAKDOWN,
        f"Product: {state.selected_name}\nConcept: {state.concept_summary}"
        f"{research_context}\n\n"
        "Break this product down into 4-8 functional modules for a BRD/PRD. "
        "One module name per line, no numbering, no descriptions. Recognize "
        "authentication/security/API-gateway concerns and label them "
        "'Platform-Core: <concern>' instead of drafting them as new modules "
        "(per BRD/PRD Section 18.6 — these are provided by platform-core, "
        "not built per project).",
        system="You are the module-breakdown step of the Idea-to-BRD/PRD Wizard.",
    )
    modules = [_strip_markdown(l.strip("-• ").strip()) for l in result["text"].splitlines() if l.strip()]
    state.modules = modules
    # Stop at the flow-design gate rather than cascading straight into
    # BRD/PRD drafting -- per the 2026-09-28 design review, generating
    # requirements before anyone has agreed on *how* each module actually
    # works (which channel, which data flow, which decisions are auto vs.
    # user-confirmed) is exactly what produced BRD/PRD content too abstract
    # for a coding agent to build from without re-iterating.
    state.stage = "flow"
    await store.save_session(state)
    return state


def _is_platform_core(module: str) -> bool:
    return module.strip().lower().startswith("platform-core")


@router.post("/flows/generate", response_model=SessionState)
async def generate_flows(req: FreezeRequest):
    """Draft a key-sequence-flow for every module that doesn't have one yet
    -- frontend + backend steps interleaved, the same shape as a manual
    tech-design pass, so the human-in-the-loop review has something concrete
    to react to rather than a bare module name."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if not state.modules:
        raise HTTPException(400, "scope not frozen yet — call /api/wizard/freeze first")

    research_context = _research_context(state)
    existing = {f.module for f in state.module_flows}

    for module in state.modules:
        if module in existing or _is_platform_core(module):
            continue
        result = await ai_router.generate(
            ai_router.Feature.TECH_DESIGN_GENERATION,
            f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n"
            f"Module: {module}{research_context}\n\n"
            "Write the key sequence flow for this module: the numbered, "
            "step-by-step path from a user's action through to the "
            "system's response, interleaving frontend (what the user sees "
            "/ does) and backend (what the service, worker, or pipeline "
            "does) steps in the order they actually happen. Be concrete "
            "and specific to this module and concept -- name the actual "
            "screens, API calls, data written, and decisions made at each "
            "step, not generic CRUD language. One step per line, numbered "
            "'1.', '2.', etc. 5-10 steps. No headers, no descriptions "
            "outside the numbered list.",
            system="You are the flow-design step of the Idea-to-BRD/PRD "
            "Wizard, run before BRD/PRD drafting so the requirement text "
            "that follows is grounded in a concrete, agreed mechanism "
            "rather than an abstract description. Plain text only.",
        )
        steps = [
            _strip_markdown(re.sub(r"^\d+[\.\)]\s*", "", l.strip()))
            for l in result["text"].splitlines()
            if l.strip()
        ]
        state.module_flows.append(ModuleFlow(module=module, steps=steps, status="Draft"))

    await store.save_session(state)
    return state


@router.post("/flows/comment", response_model=SessionState)
async def comment_flow(req: FlowCommentRequest):
    """Regenerate-from-comment for one module's flow — mirrors the BRD/PRD
    Manager's comment loop (routers/brdprd.py::comment_and_regenerate) so
    reviewers get the same familiar iterate-then-accept UX at this earlier
    gate."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    flow = next((f for f in state.module_flows if f.module == req.module), None)
    if not flow:
        raise HTTPException(404, "flow not found for module")

    current = "\n".join(f"{i+1}. {s}" for i, s in enumerate(flow.steps))
    result = await ai_router.generate(
        ai_router.Feature.REGENERATE_FROM_COMMENTS,
        f"Current sequence flow for module '{flow.module}':\n{current}\n\n"
        f"Reviewer comment: {req.comment}\n\n"
        "Rewrite the full numbered sequence flow to address the comment. "
        "Keep steps that are still correct; revise or add steps as the "
        "comment requires. Return only the revised numbered list, one step "
        "per line.",
        system="You are the flow-design step's regenerate-from-comments "
        "step. Plain text only -- no markdown bold/italics, no headers.",
    )
    revised = [
        _strip_markdown(re.sub(r"^\d+[\.\)]\s*", "", l.strip()))
        for l in result["text"].splitlines()
        if l.strip()
    ]
    flow.revised_steps = revised
    flow.status = "Revised — needs re-review"
    await store.save_session(state)
    return state


@router.post("/flows/accept", response_model=SessionState)
async def accept_flow(req: FlowModuleRequest):
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    flow = next((f for f in state.module_flows if f.module == req.module), None)
    if not flow:
        raise HTTPException(404, "flow not found for module")
    if flow.revised_steps:
        flow.steps = flow.revised_steps
        flow.revised_steps = None
    flow.status = "Approved"
    await store.save_session(state)
    return state


@router.post("/flows/discard", response_model=SessionState)
async def discard_flow(req: FlowModuleRequest):
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    flow = next((f for f in state.module_flows if f.module == req.module), None)
    if not flow:
        raise HTTPException(404, "flow not found for module")
    flow.revised_steps = None
    flow.status = "Draft"
    await store.save_session(state)
    return state


@router.post("/flows/freeze", response_model=SessionState)
async def freeze_flows(req: FlowFreezeRequest):
    """The gate itself: only once every non-Platform-Core module's flow is
    Approved does scope move on to BRD/PRD drafting."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    reviewable = [f for f in state.module_flows if not _is_platform_core(f.module)]
    not_approved = [f.module for f in reviewable if f.status != "Approved"]
    if not_approved:
        raise HTTPException(
            400,
            "these module flows still need review/approval before BRD/PRD "
            f"drafting can start: {', '.join(not_approved)}",
        )
    state.stage = "generating"
    await store.save_session(state)
    return state


@router.post("/generate", response_model=list[Requirement])
async def generate_brd_prd(req: GenerateRequest):
    """BRD/PRD requirement drafting and generation — critical tier."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if not state.modules:
        raise HTTPException(400, "scope not frozen yet — call /api/wizard/freeze first")

    generated: list[Requirement] = []
    for i, module in enumerate(state.modules, start=1):
        flow = next((f for f in state.module_flows if f.module == module), None)
        flow_context = ""
        if flow and flow.steps:
            flow_context = (
                "\n\nThis module's key sequence flow was already reviewed "
                "and approved -- draft the requirement to match this "
                "mechanism exactly rather than describing the module in the "
                "abstract:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(flow.steps))
            )
        result = await ai_router.generate(
            ai_router.Feature.BRD_PRD_DRAFTING,
            f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n"
            f"Module: {module}{flow_context}\n\n"
            "Draft the BRD/PRD requirement for this module: a short title "
            "line, then 3-5 sentences covering description, actors, and "
            "acceptance criteria. If a sequence flow is given above, the "
            "acceptance criteria must reflect its actual steps and "
            "decisions, not generic language that would fit any module.",
            system="You are the BRD/PRD generation step of the Idea-to-BRD/PRD Wizard. "
            "Plain text only -- no markdown bold/italics, no headers.",
        )
        text = result["text"].strip()
        title, _, rest = text.partition("\n")
        req_id = f"{(state.selected_name or 'PROD')[:4].upper()}-{i:03d}"
        r = Requirement(
            req_id=req_id,
            module=module,
            title=_strip_markdown(title.strip()) or module,
            body=_strip_markdown(rest.strip()) or _strip_markdown(text),
            status="Draft",
        )
        await store.add_requirement(state.session_id, r)
        generated.append(r)

    state.stage = "manager"
    await store.save_session(state)
    return generated
