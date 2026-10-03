"""
Stage 2 tail (Freeze Summary / Module Breakdown) and Stage 3 (Generating
BRD/PRD) endpoints.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from .. import ai_router, foundation, reqdoc, store
from ..locks import session_lock
from ..models import (
    ArchivedRequirementSet,
    ConsolidateRequest,
    ReopenScopeRequest,
    FlowCommentRequest,
    FlowFreezeRequest,
    FlowModuleRequest,
    FlowStepsUpdateRequest,
    ModuleBoundaryRequest,
    FreezeRequest,
    GenerateRequest,
    GenerationItem,
    GenerationProgress,
    ModuleFlow,
    ModuleSpec,
    ModulesSaveRequest,
    Requirement,
    SessionRequest,
    SessionState,
)

logger = logging.getLogger("phoneme.wizard")

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


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"```\s*$", "", text)
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b < a:
        raise ValueError("no JSON object")
    return json.loads(text[a:b + 1])


def _sync_module_names(state: SessionState) -> None:
    state.module_specs = foundation.ensure(state.module_specs)
    state.modules = [m.name for m in state.module_specs]


def _is_standard(state: SessionState, module: str) -> bool:
    return bool(foundation.key_for(state.module_specs, module))


ACCESS_TEXT = {
    "signed_in": "Only signed-in users can use this module.",
    "public": "This module is public: visitors use it without signing in (e.g. landing page, trial tool, contest).",
    "mixed": "Visitors can use a public trial part of this module without signing in; the full feature needs sign-in.",
}

STANDARD_RULE = (
    "Every GiveWings product is self-contained and already includes these "
    "STANDARD modules, written from GiveWings templates: Sign-in & Account; "
    "Profile & Settings; Admin Dashboard & Roles; Security, Audit & Health. "
    "Do NOT propose modules for sign-in/sign-up/logout, accounts, profiles, "
    "settings, admin consoles, roles/permissions, security, audit logs, "
    "health monitoring or backups -- list only the business modules specific "
    "to this product."
)


MODULE_SIZING_RULE = (
    "Use the FEWEST modules that keep responsibilities distinct: 3-4 for a "
    "small product or MVP, 5-6 for a medium one, more only for a genuinely "
    "large platform. Each module must own a distinct, non-overlapping part "
    "of the user journey -- if two modules would both describe capturing, "
    "organising or publishing the same content, merge them."
)


def module_map(state: SessionState, current: str | None = None) -> str:
    """All modules with their responsibilities, so every flow/requirement is
    written knowing its neighbours (2026-09-30: drafting each module in
    isolation made every document retell the whole product)."""
    specs = foundation.ensure(state.module_specs or [ModuleSpec(name=m) for m in state.modules])
    lines = []
    for m in specs:
        tag = " [standard module]" if m.kind == "standard" else ""
        mark = "  <-- THIS MODULE" if current and m.name == current else ""
        bound = ""
        if m.starts_when or m.outcome:
            bound = f" [starts when: {m.starts_when or '?'} -> outcome: {m.outcome or '?'}]"
        lines.append(f"- {m.name}{tag}: {_short(m.description) or 'no description'}{bound}{mark}")
    return "\n".join(lines)


def _short(text: str, words: int = 45) -> str:
    w = (text or "").split()
    return " ".join(w[:words]) + (" …" if len(w) > words else "")


BOUNDARY_RULE = (
    "Describe ONLY this module's own responsibility. Start where it receives "
    "work from another module and stop where it hands off -- refer to other "
    "modules by name instead of describing what they do. Never retell the "
    "whole product journey."
)


@router.post("/freeze", response_model=SessionState)
async def freeze_scope(req: FreezeRequest):
    """Draft the module breakdown -- critical tier. 2026-09-30: this used to
    jump straight to Flow Design, so the user never saw or agreed the
    module list. It now stops on the Freeze Scope screen, where modules can
    be renamed, described, added, removed and reordered before confirming."""
    async with session_lock(req.session_id, "freeze"):
        state = await store.get_session(req.session_id)
        if not state:
            raise HTTPException(404, "session not found")
        if state.module_specs or state.modules:
            # Existing scope (incl. sessions from before standard modules
            # existed): make sure the standard modules are present.
            if not state.module_specs:
                state.module_specs = [ModuleSpec(name=m, platform_core=_is_platform_core(m)) for m in state.modules]
            before = [m.model_dump() for m in state.module_specs]
            if state.stage == "freeze":
                _sync_module_names(state)
                if [m.model_dump() for m in state.module_specs] != before:
                    await store.save_session(state)
            return state

        research_context = _research_context(state)
        result = await ai_router.generate(
            ai_router.Feature.MODULE_BREAKDOWN,
            f"Product: {state.selected_name}\nConcept: {state.concept_summary}"
            f"{research_context}\n\n"
            "Break this product down into functional modules for a BRD/PRD, "
            "in the order they would be built. " + MODULE_SIZING_RULE + " "
            + STANDARD_RULE + " For each module say who may use it: "
            '"signed_in" (default), "public" (marketing pages, contests, free '
            'tools anyone can use without an account) or "mixed" (a public '
            "trial part plus the full feature after sign-in). Respond with ONLY "
            'JSON: {"modules": [{"name": "short module name", "description": '
            '"one sentence on what this module is responsible for", '
            '"access": "signed_in", "access_note": "what visitors can do without signing in, if public/mixed", '
            '"starts_when": "the trigger that starts this module, one short phrase", '
            '"outcome": "the concrete result this module ends with and hands on, one short phrase"}]} '
            "Boundaries must chain: each module starts where the previous one's outcome ends, and no two modules share steps.",
            system="You are the module-breakdown step of the Idea-to-BRD/PRD Wizard. JSON only.",
        )
        specs: list[ModuleSpec] = []
        try:
            data = _extract_json(result["text"])
            for m in data.get("modules", []):
                if isinstance(m, dict) and str(m.get("name", "")).strip():
                    name = re.sub(r"^platform-core:\s*", "", _strip_markdown(str(m["name"]).strip()), flags=re.I)
                    if foundation.covers(name):
                        continue
                    specs.append(_business_spec(name, m))
        except (ValueError, json.JSONDecodeError):
            for l in result["text"].splitlines():
                l = _strip_markdown(l.strip("-• ").strip())
                if l and not foundation.covers(l):
                    specs.append(ModuleSpec(name=re.sub(r"^platform-core:\s*", "", l, flags=re.I)))
        state.module_specs = specs
        _sync_module_names(state)
        await store.save_session(state)
        return state


@router.post("/modules/save", response_model=SessionState)
async def save_modules(req: ModulesSaveRequest):
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if state.stage != "freeze":
        raise HTTPException(409, "scope is already frozen")
    # Standard modules can't be removed or renamed; keep their tailoring
    # unless the request carries a new one.
    cleaned = [m for m in state.module_specs if m.kind == "standard"
               and not any(r.kind == "standard" and r.standard_key == m.standard_key for r in req.modules)]
    for m in req.modules:
        if m.kind == "standard":
            if m.standard_key in foundation.BY_KEY:
                cleaned.append(foundation.standard_spec(m.standard_key, m.tailoring.strip()))
            continue
        if not m.name.strip():
            continue
        if m.name.strip().lower() in foundation.NAMES:
            raise HTTPException(400, f"'{m.name.strip()}' is a standard module and is already included")
        cleaned.append(ModuleSpec(
            name=m.name.strip(), description=m.description.strip(), merged_from=m.merged_from,
            access=m.access if m.access in ACCESS_TEXT else "signed_in", access_note=m.access_note.strip(),
            starts_when=m.starts_when.strip(), outcome=m.outcome.strip(),
        ))
    names = [m.name.lower() for m in cleaned]
    if len(names) != len(set(names)):
        raise HTTPException(400, "module names must be unique")
    state.module_specs = cleaned
    _sync_module_names(state)
    await store.save_session(state)
    return state


@router.post("/modules/confirm", response_model=SessionState)
async def confirm_modules(req: SessionRequest):
    """User signed off the module list -- freeze scope and open Flow Design."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    _sync_module_names(state)
    if not [m for m in state.module_specs if m.kind != "standard"]:
        raise HTTPException(400, "add at least one product module before freezing scope")
    if state.stage == "freeze":
        _sync_module_names(state)
        keep = set(state.modules)
        state.module_flows = [f for f in state.module_flows if f.module in keep]
        if state.scope_revision > 0:
            # Boundaries moved -- surviving flows must be re-approved.
            for f in state.module_flows:
                if f.standard:
                    continue
                f.status = "Draft"
                f.revised_steps = None
        state.stage = "flow"
        await store.save_session(state)
    return state


def _is_platform_core(module: str) -> bool:
    return module.strip().lower().startswith("platform-core")


def _business_spec(name: str, m: dict) -> ModuleSpec:
    access = str(m.get("access") or "signed_in").strip().lower()
    return ModuleSpec(
        name=name, description=_strip_markdown(str(m.get("description", ""))),
        access=access if access in ACCESS_TEXT else "signed_in",
        access_note=_strip_markdown(str(m.get("access_note") or "")) if access != "signed_in" else "",
        starts_when=_strip_markdown(str(m.get("starts_when") or "")),
        outcome=_strip_markdown(str(m.get("outcome") or "")),
    )


@router.post("/modules/consolidate")
async def consolidate_modules(req: ConsolidateRequest):
    """AI proposal to restructure the module list (merge overlapping
    modules, hit a target count). Returned to the editor, not saved -- the
    user reviews/edits it and then saves as usual."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if state.stage != "freeze":
        raise HTTPException(409, "reopen scope before restructuring modules")
    target = f"Aim for exactly {req.target} product modules. " if req.target else ""
    result = await ai_router.generate(
        ai_router.Feature.MODULE_BREAKDOWN,
        f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n\n"
        f"Current modules:\n{module_map(state)}\n\n"
        f"Reviewer instruction: {req.instruction or 'Remove overlap and simplify.'}\n"
        f"{target}{MODULE_SIZING_RULE} {STANDARD_RULE}\n\n"
        "Propose a new list of the product (business) modules only. Every "
        "business capability of the current modules must still belong to "
        "exactly one new module. Respond with ONLY JSON: "
        '{"rationale": "2-3 sentences on what was merged and why", '
        '"modules": [{"name": "...", "description": "one sentence on what it owns", '
        '"access": "signed_in|public|mixed", "access_note": "", "starts_when": "trigger", "outcome": "end result", '
        '"merged_from": ["<current module names it replaces>"]}]}',
        system="You are a pragmatic product architect simplifying a module breakdown. JSON only.",
    )
    try:
        data = _extract_json(result["text"])
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(502, "the AI did not return a usable proposal — try again")
    specs = []
    for m in data.get("modules", []):
        if isinstance(m, dict) and str(m.get("name", "")).strip():
            name = re.sub(r"^platform-core:\s*", "", _strip_markdown(str(m["name"]).strip()), flags=re.I)
            if name.lower() in foundation.NAMES or foundation.covers(name):
                continue
            spec = _business_spec(name, m)
            spec.merged_from = [_strip_markdown(str(x)) for x in (m.get("merged_from") or []) if str(x).strip()]
            specs.append(spec)
    if not specs:
        raise HTTPException(502, "the AI did not return a usable proposal — try again")
    return {"rationale": _strip_markdown(str(data.get("rationale", ""))), "modules": [s.model_dump() for s in specs]}


@router.post("/reopen-scope", response_model=SessionState)
async def reopen_scope(req: ReopenScopeRequest):
    """Go back to Freeze Scope to redefine modules (2026-09-30 RelayReel
    review: 8 overlapping modules for a small product, with no way back).
    Drafted requirements -- including frozen ones -- are archived on the
    session, not deleted; flows are kept and matched by module name when
    the new scope is confirmed."""
    async with session_lock(req.session_id, "generate"):
        state = await store.get_session(req.session_id)
        if not state:
            raise HTTPException(404, "session not found")
        if state.stage not in ("flow", "generating", "manager"):
            raise HTTPException(409, "scope can only be reopened after it has been frozen")
        if state.generation.status == "running" and not _is_stale(state.generation):
            raise HTTPException(409, "wait for BRD/PRD drafting to finish before reopening scope")
        old = await store.clear_requirements(state.session_id)
        state = await store.get_session(req.session_id) or state
        if old:
            state.requirement_archive.append(ArchivedRequirementSet(
                archived_at=_now(), reason=req.reason or "Scope redefined",
                modules=list(state.modules), requirements=old,
            ))
        if not state.module_specs:
            state.module_specs = [ModuleSpec(name=m, platform_core=_is_platform_core(m)) for m in state.modules]
        state.module_specs = foundation.ensure(state.module_specs)
        state.generation = GenerationProgress()
        state.consistency = None
        state.scope_revision += 1
        state.stage = "freeze"
        await store.save_session(state)
        return state


@router.post("/flows/generate", response_model=SessionState)
async def generate_flows(req: FreezeRequest):
    """Draft a key-sequence-flow for every module that doesn't have one yet
    -- frontend + backend steps interleaved, the same shape as a manual
    tech-design pass, so the human-in-the-loop review has something concrete
    to react to rather than a bare module name."""
    async with session_lock(req.session_id, "flows"):
        state = await store.get_session(req.session_id)
        if not state:
            raise HTTPException(404, "session not found")
        if not state.modules:
            raise HTTPException(400, "scope not frozen yet — call /api/wizard/freeze first")
        return await _generate_flows(state)


def _ensure_standard_flows(state: SessionState) -> bool:
    """Scopes frozen before standard modules existed have no standard
    flows; add them (and the modules) so nothing is silently missing."""
    _sync_module_names(state)
    have = {f.module for f in state.module_flows}
    added = False
    for m in state.module_specs:
        if m.kind == "standard" and m.name not in have:
            state.module_flows.append(ModuleFlow(
                module=m.name, steps=foundation.flow_steps(m.standard_key, state.selected_name or "The product"),
                status="Approved", standard=True,
            ))
            added = True
    keep = set(state.modules)
    before = len(state.module_flows)
    state.module_flows = [f for f in state.module_flows if f.module in keep]
    return added or len(state.module_flows) != before


async def _generate_flows(state: SessionState) -> SessionState:
    if _ensure_standard_flows(state):
        await store.save_session(state)
    research_context = _research_context(state)
    existing = {f.module for f in state.module_flows}

    # Standard flows need no AI, so they are filled in first and at once.
    ordered = sorted(state.modules, key=lambda m: 0 if foundation.key_for(state.module_specs, m) else 1)
    for module in ordered:
        if module in existing:
            continue
        key = foundation.key_for(state.module_specs, module)
        if key:
            fresh = await store.get_session(state.session_id) or state
            if all(f.module != module for f in fresh.module_flows):
                fresh.module_flows.append(ModuleFlow(
                    module=module, steps=foundation.flow_steps(key, state.selected_name or "The product"),
                    status="Approved", standard=True,
                ))
            await store.save_session(fresh)
            state = fresh
            continue
        steps = await _draft_flow(state, module, research_context)
        # Merge into a fresh copy so approvals/edits the user made on
        # already-drafted flows while this batch runs are never overwritten.
        fresh = await store.get_session(state.session_id) or state
        if all(f.module != module for f in fresh.module_flows):
            fresh.module_flows.append(ModuleFlow(module=module, steps=steps, status="Draft"))
        await store.save_session(fresh)
        state = fresh

    return state


FLOW_STEP_RULES = (
    "Write 4-8 numbered steps, one per line ('1.', '2.', ...), no headers. "
    "Start every step with who does it, then a colon -- e.g. 'User: forwards "
    "a link to the RelayReel WhatsApp number' or 'RelayReel: saves it to the "
    "user's vault'. One short sentence per step (max 25 words). Business "
    "language only: no API endpoints, paths, HTTP methods, table/queue/field "
    "names, code identifiers, services, workers or pipelines -- those are "
    "decided later in Technical Design."
)


def _boundary_text(spec: ModuleSpec | None) -> str:
    if not spec:
        return ""
    if spec.starts_when or spec.outcome:
        return (
            "\n\nMODULE BOUNDARY (strict):\n"
            f"- The flow STARTS when: {spec.starts_when or 'this module receives work from the previous module'}\n"
            f"- The flow ENDS with this outcome: {spec.outcome or 'this module has produced its own result and handed it on'}\n"
            "Step 1 must be the start trigger and the last step must deliver the outcome. "
            "Include ONLY the steps between these two points. Anything before the start "
            "belongs to an earlier module and anything after the outcome belongs to a later "
            "module -- leave it out (at most name the next module in the last step)."
        )
    return (
        "\n\nMODULE BOUNDARY: start at the point this module receives work from the "
        "module before it and stop as soon as this module's own result exists. Do not "
        "include steps that belong to the other modules listed above."
    )


def _parse_steps(text: str) -> list[str]:
    return [
        _strip_markdown(re.sub(r"^\s*(step\s*)?\d+[\.\):]\s*", "", l.strip(), flags=re.I))
        for l in text.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]


async def _draft_flow(state: SessionState, module: str, research_context: str = "") -> list[str]:
    """One module's key sequence flow, kept inside the module's boundary
    (2026-10-01 RelayReel review: every module's flow retold the whole
    product with endpoints and table names)."""
    spec = next((m for m in state.module_specs if m.name == module), None)
    desc = f"\nWhat this module is responsible for: {spec.description}" if spec and spec.description else ""
    system = (
        "You are the flow-design step of the Idea-to-BRD/PRD Wizard. You write "
        "one module's flow only, never the whole product. Plain text only, "
        "business language."
    )
    result = await ai_router.generate(
        ai_router.Feature.TECH_DESIGN_GENERATION,
        f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n"
        f"All modules of this product, in order:\n{module_map(state, module)}\n\n"
        f"Module: {module}{desc}{_boundary_text(spec)}{research_context}\n\n"
        "Write the key sequence flow for THIS module only: the step-by-step path "
        "from its start trigger to its outcome, in the order it happens. Name the "
        "screens and decisions the user sees. " + FLOW_STEP_RULES,
        system=system,
    )
    steps = _parse_steps(result["text"])
    leaks = reqdoc.technical_leaks("\n".join(steps))
    too_long = [s for s in steps if len(s.split()) > 40]
    if leaks or too_long or len(steps) > 10:
        fix = await ai_router.generate(
            ai_router.Feature.TECH_DESIGN_GENERATION,
            f"Module: {module}{_boundary_text(spec)}\n\nThis draft flow is too technical, too long "
            f"or strays outside the module boundary ({'; '.join(leaks[:4]) or 'steps too long'}). "
            "Rewrite it within the boundary. " + FLOW_STEP_RULES + "\n\nDraft:\n"
            + "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps)),
            system=system,
        )
        fixed = _parse_steps(fix["text"])
        if fixed:
            steps = fixed
    return steps


@router.post("/modules/boundary", response_model=SessionState)
async def set_module_boundary(req: ModuleBoundaryRequest):
    """Set where a product module starts and the outcome it ends with --
    editable on Freeze Scope and in Flow Design (it does not change the
    module list, so it needs no scope reopen)."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if state.stage not in ("freeze", "flow"):
        raise HTTPException(409, "boundaries can be changed only before flows are frozen")
    spec = next((m for m in state.module_specs if m.name == req.module and m.kind != "standard"), None)
    if not spec:
        raise HTTPException(404, "product module not found")
    spec.starts_when, spec.outcome = req.starts_when.strip(), req.outcome.strip()
    await store.save_session(state)
    return state


@router.post("/modules/suggest-boundaries", response_model=SessionState)
async def suggest_boundaries(req: SessionRequest):
    """Fill in missing 'starts when' / 'outcome' for product modules from
    their descriptions, chained so each module starts where the previous
    one ends. Only empty boundaries are filled; the user then edits."""
    async with session_lock(req.session_id, "boundaries"):
        state = await store.get_session(req.session_id)
        if not state:
            raise HTTPException(404, "session not found")
        if state.stage not in ("freeze", "flow"):
            raise HTTPException(409, "boundaries can be changed only before flows are frozen")
        biz = [m for m in state.module_specs if m.kind != "standard"]
        if not any(not (m.starts_when and m.outcome) for m in biz):
            return state
        listing = "\n".join(f"{i+1}. {m.name}: {_short(m.description, 120) or 'no description'}" for i, m in enumerate(biz))
        result = await ai_router.generate(
            ai_router.Feature.MODULE_BREAKDOWN,
            f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n\n"
            f"Product modules, in journey order:\n{listing}\n\n"
            "For each module give its boundary: 'starts_when' = the trigger that starts it "
            "(one short phrase) and 'outcome' = the concrete result it ends with (one short "
            "phrase). Chain them: each module starts where the previous module's outcome "
            "ends, and no two modules cover the same steps. Business language. Respond with "
            'ONLY JSON: {"modules": [{"name": "<exact name>", "starts_when": "...", "outcome": "..."}]}',
            system="You are a pragmatic business analyst. Your job is to define module boundaries. JSON only.",
        )
        try:
            data = _extract_json(result["text"])
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(502, "the AI did not return usable boundaries — try again")
        lst = [m for m in data.get("modules", []) if isinstance(m, dict)]
        got = {str(m.get("name", "")).strip().lower(): m for m in lst}
        state = await store.get_session(req.session_id) or state
        for i, m in enumerate(x for x in state.module_specs if x.kind != "standard"):
            g = got.get(m.name.lower()) or (lst[i] if i < len(lst) else {})
            if not m.starts_when:
                m.starts_when = _strip_markdown(str(g.get("starts_when") or ""))
            if not m.outcome:
                m.outcome = _strip_markdown(str(g.get("outcome") or ""))
        await store.save_session(state)
        return state


@router.post("/flows/redraft", response_model=SessionState)
async def redraft_flow(req: FlowModuleRequest):
    """Throw away a module's flow and draft it again within its boundary."""
    async with session_lock(req.session_id, f"redraft:{req.module}"):
        state = await store.get_session(req.session_id)
        if not state:
            raise HTTPException(404, "session not found")
        if state.stage != "flow":
            raise HTTPException(409, "flows can be redrafted only during Flow Design")
        flow = next((f for f in state.module_flows if f.module == req.module), None)
        if not flow:
            raise HTTPException(404, "flow not found for module")
        if flow.standard:
            raise HTTPException(409, "standard module flows are fixed by the GiveWings template")
        steps = await _draft_flow(state, req.module, _research_context(state))
        if not steps:
            raise HTTPException(502, "the AI did not return a usable flow — try again")
        state = await store.get_session(req.session_id) or state
        flow = next(f for f in state.module_flows if f.module == req.module)
        flow.steps, flow.revised_steps, flow.status = steps, None, "Draft"
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
    if flow.standard:
        raise HTTPException(409, "standard module flows are fixed by the GiveWings template — tailor the module on Freeze Scope instead")

    current = "\n".join(f"{i+1}. {s}" for i, s in enumerate(flow.steps))
    result = await ai_router.generate(
        ai_router.Feature.REGENERATE_FROM_COMMENTS,
        f"Current sequence flow for module '{flow.module}':\n{current}"
        f"{_boundary_text(next((m for m in state.module_specs if m.name == flow.module), None))}\n\n"
        f"Reviewer comment: {req.comment}\n\n"
        "Rewrite the full numbered sequence flow to address the comment. "
        "Keep steps that are still correct; revise or add steps as the "
        "comment requires. Keep the 'Who: what happens' form and business "
        "language (no endpoints, table or field names). Return only the "
        "revised numbered list, one step per line.",
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
    if flow.standard:
        raise HTTPException(409, "standard module flows are fixed by the GiveWings template — tailor the module on Freeze Scope instead")
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
    if flow.standard:
        raise HTTPException(409, "standard module flows are fixed by the GiveWings template — tailor the module on Freeze Scope instead")
    flow.revised_steps = None
    flow.status = "Draft"
    await store.save_session(state)
    return state


@router.post("/flows/update", response_model=SessionState)
async def update_flow_steps(req: FlowStepsUpdateRequest):
    """Direct editing of a flow (2026-09-30): the user rewrites, reorders,
    inserts or deletes individual steps instead of only commenting and
    waiting for an AI rewrite. An edited flow goes back to Draft so it is
    re-approved consciously."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    flow = next((f for f in state.module_flows if f.module == req.module), None)
    if not flow:
        raise HTTPException(404, "flow not found for module")
    if flow.standard:
        raise HTTPException(409, "standard module flows are fixed by the GiveWings template — tailor the module on Freeze Scope instead")
    steps = [s.strip() for s in req.steps if s and s.strip()]
    if not steps:
        raise HTTPException(400, "a flow needs at least one step")
    flow.steps = steps
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
    if _ensure_standard_flows(state):
        await store.save_session(state)
    reviewable = [f for f in state.module_flows if not f.standard and not _is_platform_core(f.module)]
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


_running_tasks: set[asyncio.Task] = set()
STALE_AFTER = timedelta(minutes=10)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_stale(g: GenerationProgress) -> bool:
    if not g.updated_at:
        return True
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(g.updated_at) > STALE_AFTER
    except ValueError:
        return True


@router.post("/generate", response_model=SessionState)
async def generate_brd_prd(req: GenerateRequest):
    """Start (or resume) BRD/PRD drafting -- critical tier.

    2026-09-30: this used to be one blocking call that drafted every module
    before answering, so the browser showed "in progress" with no numbers
    and could lose the response entirely. It now returns immediately and
    drafts in the background, recording per-document progress on the
    session (generation.items) that the UI polls. Already-drafted modules
    are skipped, so a restart resumes rather than starting over, and a
    second tab can never start a second run."""
    async with session_lock(req.session_id, "generate"):
        state = await store.get_session(req.session_id)
        if not state:
            raise HTTPException(404, "session not found")
        if not state.modules:
            raise HTTPException(400, "scope not frozen yet — call /api/wizard/freeze first")
        g = state.generation
        if g.status == "running" and not _is_stale(g):
            return state
        if g.status == "done":
            return state

        existing = {r.module: r for r in await store.list_requirements(state.session_id)}
        items = []
        for i, module in enumerate(state.modules, start=1):
            req_id = f"{(state.selected_name or 'PROD')[:4].upper()}-{i:03d}"
            if module in existing:
                items.append(GenerationItem(module=module, req_id=existing[module].req_id, status="done"))
            else:
                items.append(GenerationItem(module=module, req_id=req_id, status="queued"))
        state.generation = GenerationProgress(
            status="running", total=len(items), done=sum(1 for it in items if it.status == "done"),
            items=items, started_at=_now(), updated_at=_now(),
        )
        state.stage = "generating"
        await store.save_session(state)

        task = asyncio.create_task(_run_generation(state.session_id))
        _running_tasks.add(task)
        task.add_done_callback(_running_tasks.discard)
        return state


async def _run_generation(session_id: str) -> None:
    state = await store.get_session(session_id)
    if not state:
        return
    for item in state.generation.items:
        if item.status == "done":
            continue
        item.status = "drafting"
        state.generation.updated_at = _now()
        await store.save_session(state)
        try:
            r = await _draft_requirement(state, item.module, item.req_id)
            await store.add_requirement(session_id, r)
            item.status = "done"
            state.generation.done += 1
        except Exception as exc:
            logger.exception("BRD/PRD drafting failed for %s / %s", session_id, item.module)
            item.status = "failed"
            item.error = f"{type(exc).__name__}: {str(exc)[:200]}"
        state.generation.updated_at = _now()
        await store.save_session(state)

    failed = [it for it in state.generation.items if it.status == "failed"]
    state.generation.status = "failed" if failed else "done"
    state.generation.updated_at = _now()
    if not failed:
        state.stage = "manager"
    await store.save_session(state)


@router.post("/generate/retry", response_model=SessionState)
async def retry_generation(req: SessionRequest):
    """Re-queue failed documents only."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    for it in state.generation.items:
        if it.status == "failed":
            it.status, it.error = "queued", ""
    state.generation.status = "idle"
    await store.save_session(state)
    return await generate_brd_prd(GenerateRequest(session_id=req.session_id))


async def _draft_requirement(state: SessionState, module: str, req_id: str) -> Requirement:
    key = foundation.key_for(state.module_specs, module)
    if key:
        spec = next(m for m in state.module_specs if m.standard_key == key)
        public = "; ".join(
            f"{m.name}: {m.access_note or ACCESS_TEXT[m.access]}"
            for m in state.module_specs if m.kind != "standard" and m.access in ("public", "mixed")
        )
        title, doc = await foundation.tailored_doc(
            key, state.selected_name or "The product", state.concept_summary or "",
            spec.tailoring, public, module_map(state, module),
        )
        return Requirement(
            req_id=req_id, module=module, title=title, body=reqdoc.render_text(title, doc),
            status="Draft", doc=doc, standard_version=foundation.STANDARD_VERSION,
        )
    flow = next((f for f in state.module_flows if f.module == module), None)
    spec = next((m for m in state.module_specs if m.name == module or f"Platform-Core: {m.name}" == module), None)
    ctx = ""
    if spec and spec.description:
        ctx += f"\nModule responsibility: {spec.description}"
    if spec and (spec.starts_when or spec.outcome):
        ctx += (
            f"\nBoundary: this module starts when {spec.starts_when or 'it receives work from the previous module'} "
            f"and ends with: {spec.outcome or 'its own result'}. The journey covers only that span; "
            "use receives_from / hands_off_to for what lies outside it."
        )
    if spec:
        ctx += f"\nWho can use it: {ACCESS_TEXT.get(spec.access, ACCESS_TEXT['signed_in'])}"
        if spec.access_note:
            ctx += f" Without signing in, visitors can: {spec.access_note}"
    ctx += (
        "\nSign-in, profiles, settings, admin and roles, security, audit and "
        "health monitoring are covered by the product's standard modules -- "
        "refer to them by name where relevant; do not specify them here."
    )
    if flow and flow.steps:
        ctx += (
            "\n\nThis module's key sequence flow was reviewed and approved "
            "by the business -- the journey and acceptance criteria must "
            "follow it exactly (restate it in business language if any "
            "step is technical):\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(flow.steps))
        )
    if _is_platform_core(module):
        ctx += (
            "\n\nThis is a Platform-Core module provided by the shared "
            "platform. Describe only what this product needs from it "
            "(who signs in, what they may access), not how it is built."
        )
    title, doc = await reqdoc.generate_doc(
        f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n"
        f"All modules of this product:\n{module_map(state, module)}\n\nModule: {module}{ctx}\n\n"
        "Write the BRD/PRD requirement for this module. " + BOUNDARY_RULE,
        fallback_title=module,
    )
    return Requirement(
        req_id=req_id, module=module, title=title, body=reqdoc.render_text(title, doc),
        status="Draft", doc=doc,
    )
