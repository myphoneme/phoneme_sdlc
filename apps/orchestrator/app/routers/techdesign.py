"""
Stage 8 -- Technical Design (HLD/LLD), Phoneme SDLC Stage 2 (2026-10-04).

Order of work, per Phoneme's techdesign + technical-stack standards:
  1. Technical Stack Charter: AI suggests, the user edits and CONFIRMS it
     (never assumed silently). Every design section references it.
  2. HLD (system architecture) + one LLD per BRD/PRD module, numbered 1:1
     with the BRD/PRD for traceability (RELA-002 -> RELA-TD-002).
  3. Same review loop as the BRD/PRD (review.py), baseline, Word export.
This is where API contracts, data models and technical sequences belong --
they were deliberately kept out of the business-language BRD/PRD.
"""
import json
import re

from fastapi import HTTPException
from fastapi.responses import Response

from .. import ai_router, export as exporter, reqdoc, review, store
from ..models import (
    SessionState, StackCharter, StackSaveRequest, TDApi, TDComponent, TDEntity, TDField,
    TDNfr, TechDesign, TechDoc,
)

STACK_FIELDS = [
    ("product_type", "Product type"), ("frontend", "Frontend"), ("backend", "Backend"),
    ("data", "Data"), ("ai_ml", "AI / ML components"), ("hosting", "Hosting & infra"),
    ("integrations", "Third-party integrations"), ("devops", "DevOps & CI/CD"),
    ("security", "Security & compliance baseline"), ("conventions", "Coding conventions"),
]


def code(state: SessionState) -> str:
    return exporter.product_code(state)


def stack_text(s: StackCharter | None) -> str:
    if not s:
        return "(no stack charter)"
    return "\n".join(f"- {label}: {getattr(s, k) or 'TBD'}" for k, label in STACK_FIELDS)


def _s(x) -> str:
    return reqdoc._clean(x) if x is not None else ""


def _list(x) -> list[str]:
    return [_s(i) for i in (x or []) if _s(i)] if isinstance(x, list) else []


def parse_techdoc(d: dict) -> TechDoc:
    def comps(v):
        out = []
        for c in v or []:
            if isinstance(c, dict) and _s(c.get("name")):
                out.append(TDComponent(name=_s(c["name"]), responsibility=_s(c.get("responsibility"))))
        return out
    ents = []
    for e in d.get("data_model") or []:
        if isinstance(e, dict) and _s(e.get("name")):
            fields = [TDField(name=_s(f.get("name")), type=_s(f.get("type")), notes=_s(f.get("notes")))
                      for f in (e.get("fields") or []) if isinstance(f, dict) and _s(f.get("name"))]
            ents.append(TDEntity(name=_s(e["name"]), description=_s(e.get("description")), fields=fields))
    apis = []
    for a in d.get("apis") or []:
        if isinstance(a, dict) and _s(a.get("path")):
            m = _s(a.get("method")).upper() or "GET"
            apis.append(TDApi(method=m if m in ("GET", "POST", "PUT", "PATCH", "DELETE") else "POST", path=_s(a["path"]),
                              purpose=_s(a.get("purpose")), request=_s(a.get("request")), response=_s(a.get("response"))))
    nfr = []
    for n in d.get("nfr") or []:
        if isinstance(n, dict) and _s(n.get("requirement")):
            nfr.append(TDNfr(requirement=_s(n["requirement"]), approach=_s(n.get("approach"))))
        elif isinstance(n, str) and n.strip():
            nfr.append(TDNfr(requirement=_s(n)))
    seq = [re.sub(r"^\s*\d+[\.\)]\s*", "", x) for x in _list(d.get("sequence"))]
    return TechDoc(
        overview=_s(d.get("overview")), components=comps(d.get("components")), data_model=ents, apis=apis,
        sequence=seq, edge_cases=_list(d.get("edge_cases")), integrations=_list(d.get("integrations")),
        security=_list(d.get("security")), nfr=nfr, risks=_list(d.get("risks")),
        open_questions=_list(d.get("open_questions"))[:6],
    )


SCHEMA_LLD = """Respond with ONLY one JSON object:
{
  "overview": "<2-4 sentences: what this module does technically and how it fits the architecture>",
  "components": [{"name": "<service/UI/worker>", "responsibility": "<one sentence>"}],
  "data_model": [{"name": "<Entity>", "description": "<one sentence>", "fields": [{"name": "<field>", "type": "<type>", "notes": "<key/constraint/notes>"}]}],
  "apis": [{"method": "GET|POST|PUT|PATCH|DELETE", "path": "/api/...", "purpose": "<one sentence>", "request": "<main inputs>", "response": "<main outputs>"}],
  "sequence": ["<numbered technical step: who calls whom, in order>"],
  "edge_cases": ["<edge case -> how it is handled>"],
  "security": ["<auth/permission/data-protection point for this module>"],
  "nfr": [{"requirement": "<BRD/PRD non-functional need>", "approach": "<how this module meets it>"}],
  "open_questions": ["<only real technical decisions the product owner/architect must still make>"]
}
Be concrete and consistent with the stack charter. 3-8 entities, 4-12 APIs, 6-12 sequence steps."""

SCHEMA_HLD = """Respond with ONLY one JSON object:
{
  "overview": "<3-6 sentences: overall system architecture, how requests flow, how AI is used, how it is hosted>",
  "components": [{"name": "<system component>", "responsibility": "<one sentence>"}],
  "integrations": ["<third-party/system integration and what it is used for>"],
  "security": ["<auth model, data at rest/in transit, PII handling, applicable regulation>"],
  "nfr": [{"requirement": "<performance/scalability/availability/compliance/localization need>", "approach": "<how the architecture achieves it>"}],
  "sequence": ["<the main end-to-end technical flow across modules, step by step>"],
  "risks": ["<technical risk -> mitigation>"],
  "open_questions": ["<only real architecture decisions still to be made>"]
}"""


async def _req(session_id: str, req_id: str):
    return await store.get_requirement(session_id, req_id) if req_id else None


async def plan(state: SessionState) -> list:
    if state.tech_designs:
        return []
    c = code(state)
    reqs = sorted(await store.list_requirements(state.session_id), key=lambda r: r.req_id)
    out = [TechDesign(td_id=f"{c}-TD-000", module="System architecture (HLD)", kind="hld",
                      title="System architecture (HLD)")]
    for r in reqs:
        num = r.req_id.split("-")[-1]
        out.append(TechDesign(td_id=f"{c}-TD-{num}", module=r.module, req_id=r.req_id, title=r.title, kind="lld"))
    return out


async def draft(state: SessionState, item: TechDesign, instruction: str | None) -> TechDoc:
    reqs = sorted(await store.list_requirements(state.session_id), key=lambda r: r.req_id)
    head = (f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n"
            f"Market: {(state.concept_brief.market if state.concept_brief else '') or 'not stated'}\n\n"
            f"Technical Stack Charter (confirmed -- follow it):\n{stack_text(state.stack)}\n\n")
    if item.kind == "hld":
        digest = "\n".join(f"- {r.req_id} {r.title} (module: {r.module}){' [GiveWings standard module]' if r.standard_version else ''}: {r.doc.summary if r.doc else ''}" for r in reqs)
        prompt = head + f"BRD/PRD modules (baselined):\n{digest}\n\nWrite the High-Level Design for the whole product. Every product is self-contained and ships its own sign-in, profile, admin, security/audit and a health agent that reports to the GiveWings Health Dashboard.\n\n" + SCHEMA_HLD
    else:
        r = await _req(state.session_id, item.req_id)
        brd = reqdoc.render_text(r.title, r.doc) if r and r.doc else (r.body if r else "")
        others = "\n".join(f"- {x.req_id} {x.title} ({x.module})" for x in reqs if x.req_id != item.req_id)
        std = " This is a GiveWings standard module: use proven, conventional patterns." if r and r.standard_version else ""
        prompt = head + (f"Other modules (design only THIS one; call theirs by name):\n{others}\n\n"
                         f"BRD/PRD requirement {item.req_id} (baselined -- the design must satisfy every acceptance criterion):\n{brd}\n\n"
                         f"Write the Low-Level Design for this module.{std}\n\n" + SCHEMA_LLD)
    if instruction and item.doc:
        prompt += "\n\nCurrent design:\n" + json.dumps(item.doc.model_dump(), ensure_ascii=False) + f"\n\n{instruction}"
    result = await ai_router.generate(
        ai_router.Feature.TECH_DESIGN_GENERATION, prompt,
        system="You are a senior solution architect writing Phoneme's Technical Design Document (HLD/LLD). JSON only, no markdown.",
    )
    try:
        return parse_techdoc(reqdoc._extract_json(result["text"]))
    except (ValueError, json.JSONDecodeError):
        raise RuntimeError("the AI did not return a usable technical design")


def ready(state: SessionState) -> str | None:
    if not any(b.doc_type == "brdprd" for b in state.baselines):
        return "baseline the BRD/PRD before starting Technical Design"
    if not (state.stack and state.stack.confirmed):
        return "confirm the Technical Stack Charter first"
    return None


KIND = review.Kind(
    doc_type="techdesign", label="Technical Design", list_attr="tech_designs", id_attr="td_id",
    gen_attr="tech_generation", stage="techdesign", next_stage="uiux", plan=plan, draft=draft,
    record_deferred=lambda doc, t: doc.risks.append(f"Deferred to a later release: {t}"), ready=ready,
)
router = review.make_router(KIND)


@router.post("/{session_id}/stack/suggest", response_model=SessionState)
async def suggest_stack(session_id: str):
    state = await review._session(session_id)
    if state.stack and state.stack.confirmed:
        raise HTTPException(409, "the stack charter is already confirmed")
    brief = state.concept_brief
    mods = "\n".join(f"- {m.name}: {m.description[:200]}" for m in state.module_specs if m.kind != "standard")
    result = await ai_router.generate(
        ai_router.Feature.TECH_DESIGN_GENERATION,
        f"Product: {state.selected_name}\nConcept: {state.concept_summary}\n"
        f"Market: {(brief.market if brief else '') or 'not stated'}; platforms: {(brief.platforms if brief else '') or 'not stated'}; "
        f"input channels: {(brief.input_channels if brief else '') or 'not stated'}\nProduct modules:\n{mods}\n\n"
        "Suggest a Technical Stack Charter for this product. Sensible, mainstream, maintainable choices; "
        "mark anything that really needs the owner's decision as 'TBD — confirm: <options>'. Include data "
        "residency and the applicable data-protection law for the market. Respond with ONLY JSON with these keys, "
        "each a short paragraph or list in one string: " + ", ".join(k for k, _ in STACK_FIELDS),
        system="You are a pragmatic solution architect proposing a technology stack. JSON only.",
    )
    try:
        data = reqdoc._extract_json(result["text"])
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(502, "the AI did not return a usable stack suggestion — try again")
    state = await review._session(session_id)
    cur = state.stack or StackCharter()
    for k, _ in STACK_FIELDS:
        v = data.get(k)
        if isinstance(v, list):
            v = "; ".join(str(x) for x in v)
        if v and not getattr(cur, k):
            setattr(cur, k, _s(v))
    state.stack = cur
    await store.save_session(state)
    return state


@router.post("/{session_id}/stack", response_model=SessionState)
async def save_stack(session_id: str, req: StackSaveRequest):
    state = await review._session(session_id)
    old = state.stack or StackCharter()
    new = req.stack.model_copy(update={"confirmed": old.confirmed, "confirmed_at": old.confirmed_at, "changelog": old.changelog})
    if old.confirmed:
        changed = [label for k, label in STACK_FIELDS if getattr(old, k) != getattr(new, k)]
        if changed:
            new.changelog = old.changelog + [f"{review.now()[:10]}: changed {', '.join(changed)}"]
    state.stack = new
    await store.save_session(state)
    return state


@router.post("/{session_id}/stack/confirm", response_model=SessionState)
async def confirm_stack(session_id: str):
    state = await review._session(session_id)
    s = state.stack
    if not s or not all(getattr(s, k).strip() for k, _ in STACK_FIELDS[:6]):
        raise HTTPException(400, "fill in at least product type, frontend, backend, data, AI/ML and hosting")
    tbd = [label for k, label in STACK_FIELDS if "tbd" in getattr(s, k).lower()]
    if tbd:
        raise HTTPException(400, "decide the items still marked TBD: " + ", ".join(tbd))
    s.confirmed, s.confirmed_at = True, review.now()
    s.changelog = s.changelog + [f"{s.confirmed_at[:10]}: charter confirmed"]
    await store.save_session(state)
    return state


@router.get("/{session_id}/export/techdesign.docx")
async def export_techdesign(session_id: str):
    state = await review._session(session_id)
    if not state.tech_designs:
        raise HTTPException(400, "no technical design to export yet")
    reqs = sorted(await store.list_requirements(session_id), key=lambda r: r.req_id)
    data, filename = exporter.techdesign_docx(state, reqs)
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
