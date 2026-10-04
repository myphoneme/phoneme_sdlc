"""
Stage 9 -- UI/UX screens (Phoneme SDLC Stage 3), 2026-10-04.

One screen set per BRD/PRD module (traceable: RELA-002 -> RELA-UI-002),
drawn in the product's own brand from the Identity step (palette, logo,
tagline, domain). Screens are structured specs rendered server-side
(ui_render.py), so the portal preview and the exported mockup file are the
same thing. Same review loop and baseline as the other stages.
"""
import json

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from .. import ai_router, reqdoc, review, store, ui_render
from ..models import SessionState, UIBlock, UIDoc, UIModule, UIScreen

BLOCK_TYPES = {"header", "text", "list", "cards", "form", "buttons", "table", "tabs", "stats", "notice", "steps", "media"}

SCHEMA = """Respond with ONLY one JSON object:
{
  "screens": [
    {"name": "<screen name>", "purpose": "<one sentence: what the user does here>", "route": "/path",
     "layout": "app|public|mobile",
     "blocks": [
       {"type": "header|text|list|cards|form|buttons|table|tabs|stats|notice|steps|media",
        "title": "<optional heading>", "text": "<optional text>",
        "items": ["<list rows / card 'Title — detail' / form field labels / tab names / 'Stat label: value' / step names>"],
        "columns": ["<table columns>"], "rows": [["<table cells>"]],
        "actions": ["<button labels, primary first>"]}
     ],
     "states": ["<empty / loading / error state and what the user sees>"]}
  ],
  "notes": ["<design decision worth recording>"],
  "open_questions": ["<only real UX decisions the product owner must still make>"]
}
2-5 screens covering the module's journey in order; 3-8 blocks per screen with REALISTIC sample content
for this product (real-looking names, items and numbers -- never lorem ipsum). Use layout "public" only for
screens visitors use without signing in."""


async def plan(state: SessionState) -> list:
    if state.ui_modules:
        return []
    from .techdesign import code
    c = code(state)
    reqs = sorted(await store.list_requirements(state.session_id), key=lambda r: r.req_id)
    return [UIModule(ui_id=f"{c}-UI-{r.req_id.split('-')[-1]}", module=r.module, req_id=r.req_id, title=r.title) for r in reqs]


def parse(d: dict) -> UIDoc:
    def s(x):
        return reqdoc._clean(x) if x is not None else ""
    screens = []
    for i, sc in enumerate(d.get("screens") or [], 1):
        if not isinstance(sc, dict) or not s(sc.get("name")):
            continue
        blocks = []
        for b in sc.get("blocks") or []:
            if not isinstance(b, dict):
                continue
            t = s(b.get("type")).lower()
            blocks.append(UIBlock(
                type=t if t in BLOCK_TYPES else "text", title=s(b.get("title")), text=s(b.get("text")),
                items=[s(x) for x in (b.get("items") or []) if s(x)][:12],
                columns=[s(x) for x in (b.get("columns") or [])][:8],
                rows=[[s(c) for c in row][:8] for row in (b.get("rows") or []) if isinstance(row, list)][:8],
                actions=[s(x) for x in (b.get("actions") or []) if s(x)][:4],
            ))
        lay = s(sc.get("layout")).lower()
        screens.append(UIScreen(screen_id=f"S{i}", name=s(sc["name"]), purpose=s(sc.get("purpose")),
                                route=s(sc.get("route")), layout=lay if lay in ("app", "public", "mobile") else "app",
                                blocks=blocks, states=[s(x) for x in (sc.get("states") or []) if s(x)][:5]))
    return UIDoc(screens=screens, notes=[s(x) for x in (d.get("notes") or []) if s(x)],
                 open_questions=[s(x) for x in (d.get("open_questions") or []) if s(x)][:6])


async def draft(state: SessionState, item: UIModule, instruction: str | None) -> UIDoc:
    r = await store.get_requirement(state.session_id, item.req_id)
    brd = reqdoc.render_text(r.title, r.doc) if r and r.doc else (r.body if r else "")
    td = next((t for t in state.tech_designs if t.req_id == item.req_id and t.doc), None)
    apis = "\n".join(f"- {a.method} {a.path}: {a.purpose}" for a in (td.doc.apis if td else []))
    spec = next((m for m in state.module_specs if m.name == item.module), None)
    access = {"public": "public (no sign-in)", "mixed": "public trial part + full feature after sign-in"}.get(spec.access if spec else "", "signed-in users")
    pal = state.brand.palette if state.brand else None
    prompt = (
        f"Product: {state.selected_name} — {state.brand.tagline if state.brand and state.brand.tagline else ''}\n"
        f"Concept: {state.concept_summary}\nBrand palette: {pal.name + ' ' + pal.mood if pal else 'default'}\n"
        f"Platforms: {(state.concept_brief.platforms if state.concept_brief else '') or 'web'}\n"
        f"Module: {item.module} ({item.req_id}); who can use it: {access}\n\n"
        f"Baselined BRD/PRD requirement:\n{brd}\n\n"
        + (f"Technical Design API contracts for this module (screens must be buildable on these):\n{apis}\n\n" if apis else "")
        + "Design the screens for this module only. " + SCHEMA
    )
    if instruction and item.doc:
        prompt += "\n\nCurrent screens:\n" + json.dumps(item.doc.model_dump(), ensure_ascii=False) + f"\n\n{instruction}"
    result = await ai_router.generate(
        ai_router.Feature.TECH_DESIGN_GENERATION, prompt,
        system="You are a senior product designer producing structured UI screen specs for a mockup system. JSON only.",
    )
    try:
        doc = parse(reqdoc._extract_json(result["text"]))
    except (ValueError, json.JSONDecodeError):
        raise RuntimeError("the AI did not return usable screens")
    if not doc.screens:
        raise RuntimeError("the AI returned no screens")
    return doc


def ready(state: SessionState) -> str | None:
    if not any(b.doc_type == "techdesign" for b in state.baselines):
        return "baseline the Technical Design before starting UI/UX"
    return None


KIND = review.Kind(
    doc_type="uiux", label="UI/UX", list_attr="ui_modules", id_attr="ui_id", gen_attr="ui_generation",
    stage="uiux", next_stage="complete", plan=plan, draft=draft,
    record_deferred=lambda doc, t: doc.notes.append(f"Deferred to a later release: {t}"), ready=ready,
)
router = review.make_router(KIND)


@router.get("/{session_id}/render/{ui_id}", response_class=HTMLResponse)
async def render_module(session_id: str, ui_id: str, revised: int = 0):
    state = await review._session(session_id)
    m = review.find(KIND, state, ui_id)
    return HTMLResponse(ui_render.page(state, [m], revised=bool(revised)))


@router.get("/{session_id}/export/mockups.html")
async def export_mockups(session_id: str):
    state = await review._session(session_id)
    if not any(m.doc for m in state.ui_modules):
        raise HTTPException(400, "no screens to export yet")
    v = [b.version for b in state.baselines if b.doc_type == "uiux"]
    from .techdesign import code
    name = f"PHN-{code(state)}-UIUX_v{v[-1] if v else 'draft'}.html"
    return HTMLResponse(ui_render.page(state, [m for m in state.ui_modules if m.doc]),
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})
