"""
Stage 2 tail (Freeze Summary / Module Breakdown) and Stage 3 (Generating
BRD/PRD) endpoints.
"""
import re

from fastapi import APIRouter, HTTPException

from .. import ai_router, store
from ..models import FreezeRequest, GenerateRequest, Requirement, SessionState

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


@router.post("/freeze", response_model=SessionState)
async def freeze_scope(req: FreezeRequest):
    """Module-breakdown drafting that freezes scope — critical tier."""
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")

    research_context = ""
    if state.research and state.research.recommended_features:
        research_context = (
            "\n\nCompetitive research already surfaced these recommended "
            "features -- ground the module breakdown in them rather than "
            "inventing scope from scratch, mapping each feature to whichever "
            "module it belongs under:\n- "
            + "\n- ".join(state.research.recommended_features)
        )
        if state.research.risks:
            research_context += (
                "\n\nAlso known constraints/risks to keep modules realistic "
                "about:\n- " + "\n- ".join(state.research.risks)
            )
        if state.research.killer_feature:
            research_context += (
                "\n\nThe research identified this as the product's central "
                "differentiator -- make sure it has an obvious home in the "
                "module breakdown, not buried as an afterthought inside a "
                "generic module: " + state.research.killer_feature
            )
        if state.research.positioning_reframe:
            research_context += (
                "\n\nPositioning to keep in mind while naming/scoping "
                "modules: " + state.research.positioning_reframe
            )

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
    state.stage = "generating"
    store.save_session(state)
    return state


@router.post("/generate", response_model=list[Requirement])
async def generate_brd_prd(req: GenerateRequest):
    """BRD/PRD requirement drafting and generation — critical tier."""
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if not state.modules:
        raise HTTPException(400, "scope not frozen yet — call /api/wizard/freeze first")

    generated: list[Requirement] = []
    for i, module in enumerate(state.modules, start=1):
        result = await ai_router.generate(
            ai_router.Feature.BRD_PRD_DRAFTING,
            f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n"
            f"Module: {module}\n\n"
            "Draft the BRD/PRD requirement for this module: a short title "
            "line, then 3-5 sentences covering description, actors, and "
            "acceptance criteria.",
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
        store.add_requirement(state.session_id, r)
        generated.append(r)

    state.stage = "manager"
    store.save_session(state)
    return generated
