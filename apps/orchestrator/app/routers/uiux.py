"""
Stage 9 -- UI/UX screens (Phoneme SDLC Stage 3), 2026-10-04.

One screen set per BRD/PRD module (traceable: RELA-002 -> RELA-UI-002),
drawn in the product's own brand from the Identity step (palette, logo,
tagline, domain). Screens are structured specs rendered server-side
(ui_render.py), so the portal preview and the exported mockup file are the
same thing. Same review loop and baseline as the other stages.
"""
import base64
import json
import re
import uuid
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from .. import ai_router, config, export, reqdoc, review, store, ui_render
from ..locks import session_lock
from ..models import ScreenEditRequest, ScreenMoveRequest, SessionState, UIBlock, UIDoc, UIModule, UIScreen

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
        "actions": ["<button label, primary first; to show where it leads write 'Label -> Exact screen name'>"]}
     ],
     "states": ["<empty / loading / error state and what the user sees>"]}
  ],
  "notes": ["<design decision worth recording>"],
  "open_questions": ["<only real UX decisions the product owner must still make>"]
}
2-5 screens covering the module's journey in order; 3-8 blocks per screen with REALISTIC sample content
for this product (real-looking names, items and numbers -- never lorem ipsum). Use layout "public" only for
screens visitors use without signing in. Make the screens a navigable flow: the primary button on each
screen should lead to the next step ('Continue -> <next screen name>'); secondary buttons may lead back or
to another screen of this module."""


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
            acts, tgts = [], []
            for a in (b.get("actions") or [])[:4]:
                a = s(a)
                if not a:
                    continue
                label, _, tgt = a.partition("->")
                acts.append(label.strip())
                tgts.append(tgt.strip())
            blocks.append(UIBlock(
                type=t if t in BLOCK_TYPES else "text", title=s(b.get("title")), text=s(b.get("text")),
                items=[s(x) for x in (b.get("items") or []) if s(x)][:12],
                columns=[s(x) for x in (b.get("columns") or [])][:8],
                rows=[[s(c) for c in row][:8] for row in (b.get("rows") or []) if isinstance(row, list)][:8],
                actions=acts, targets=tgts,
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
        cur = item.doc.model_copy(update={"screens": [x for x in item.doc.screens if x.source != "upload"]})
        prompt += "\n\nCurrent screens:\n" + json.dumps(cur.model_dump(), ensure_ascii=False) + f"\n\n{instruction}"
    uploaded = [x.name for x in (item.doc.screens if item.doc else []) if x.source == "upload"]
    if uploaded:
        prompt += ("\n\nThe product owner uploaded their own designs for: " + "; ".join(uploaded)
                   + ". Do not redesign those screens; design only what is still missing and link to them by name.")
    result = await ai_router.generate(
        ai_router.Feature.TECH_DESIGN_GENERATION, prompt,
        system="You are a senior product designer producing structured UI screen specs for a mockup system. JSON only.",
    )
    try:
        doc = parse(reqdoc._extract_json(result["text"]))
    except (ValueError, json.JSONDecodeError):
        raise RuntimeError("the AI did not return usable screens")
    if not doc.screens and not uploaded:
        raise RuntimeError("the AI returned no screens")
    return merge(item.doc, doc)


def merge(old: UIDoc | None, new: UIDoc) -> UIDoc:
    """Uploaded designs always survive an AI draft or rework, in place."""
    if not old:
        return new
    have = {x.screen_id for x in new.screens}
    ups = [x for x in old.screens if x.source == "upload" and x.screen_id not in have]
    if not ups:
        return new
    out = list(new.screens)
    for u in ups:  # keep each upload at its old position (clamped)
        out.insert(min(old.screens.index(u), len(out)), u)
    return new.model_copy(update={"screens": out})


def ready(state: SessionState) -> str | None:
    if not any(b.doc_type == "techdesign" for b in state.baselines):
        return "baseline the Technical Design before starting UI/UX"
    return None


KIND = review.Kind(
    doc_type="uiux", label="UI/UX", list_attr="ui_modules", id_attr="ui_id", gen_attr="ui_generation",
    stage="uiux", next_stage="complete", plan=plan, draft=draft,
    record_deferred=lambda doc, t: doc.notes.append(f"Deferred to a later release: {t}"), ready=ready,
    merge=merge,
    on_baseline=lambda state: __import__("app.documents", fromlist=["archive"]).archive(state, "uiux"),
)
router = review.make_router(KIND)


# ---------------------------------------------------------------- uploads
SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"), (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"), (b"GIF89a", "image/gif", "gif"), (b"%PDF-", "application/pdf", "pdf"),
]
MAX_UPLOAD_SCREENS = 30


def _sniff(data: bytes):
    """Detect the type from the file's bytes, not its name (SVG/HTML are
    refused: they can carry scripts)."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    for sig, mime, ext in SIGNATURES:
        if data.startswith(sig):
            return mime, ext
    return None, None


def _dir(session_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", session_id):
        raise HTTPException(400, "bad session id")
    return config.UPLOAD_DIR / session_id


def _asset_path(session_id: str, screen: UIScreen) -> Path:
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "application/pdf": "pdf"}
    mime = screen.blocks[0].title if screen.blocks else ""
    return _dir(session_id) / f"{screen.asset_id}.{ext.get(mime, 'bin')}"


def _editable(item: UIModule) -> None:
    if item.status == "Frozen":
        raise HTTPException(409, "unfreeze this module to change its screens")
    if item.revised_doc is not None:
        raise HTTPException(409, "accept or discard the pending revision first")


def _touched(item: UIModule) -> None:
    if item.status == "Approved":
        item.status = "Draft"  # changed screens need re-approval


@router.post("/{session_id}/upload/{ui_id}", response_model=SessionState)
async def upload_designs(session_id: str, ui_id: str, files: list[UploadFile] = File(...),
                         mode: str = Form("add"), name: str = Form("")):
    """Add the owner's own designs (PNG/JPG/WebP/GIF/PDF) as screens of a
    module. mode=replace removes the AI-drafted screens of that module."""
    async with session_lock(session_id, f"uiux:{ui_id}"):
        state = await review._session(session_id)
        item = review.find(KIND, state, ui_id)
        _editable(item)
        doc = item.doc or UIDoc()
        if len([x for x in doc.screens if x.source == "upload"]) + len(files) > MAX_UPLOAD_SCREENS:
            raise HTTPException(400, f"at most {MAX_UPLOAD_SCREENS} uploaded designs per module")
        folder = _dir(session_id)
        folder.mkdir(parents=True, exist_ok=True)
        new = []
        for f in files:
            data = await f.read(config.UPLOAD_MAX_BYTES + 1)
            if len(data) > config.UPLOAD_MAX_BYTES:
                raise HTTPException(413, f"{f.filename}: larger than {config.UPLOAD_MAX_BYTES // (1024 * 1024)} MB")
            mime, ext = _sniff(data)
            if not mime:
                raise HTTPException(415, f"{f.filename}: upload PNG, JPG, WebP, GIF or PDF")
            fid = uuid.uuid4().hex[:16]
            (folder / f"{fid}.{ext}").write_bytes(data)
            stem = re.sub(r"[_-]+", " ", Path(f.filename or "Design").stem).strip()[:60] or "Design"
            label = (name.strip() if name.strip() and len(files) == 1 else stem)
            slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "design"
            new.append(UIScreen(screen_id=f"U{fid[:8]}", name=label, purpose="Uploaded design", layout="image", route=f"/{slug}",
                                source="upload", asset_id=fid, blocks=[UIBlock(type="image", title=mime, text=fid)]))
        kept = [x for x in doc.screens if x.source == "upload"] if mode == "replace" else list(doc.screens)
        item.doc = doc.model_copy(update={"screens": kept + new})
        _touched(item)
        item.thread.append(review.ReviewMessage(role="owner", at=review.now(),
                           text=f"Uploaded {len(new)} design{'s' if len(new) != 1 else ''}: " + ", ".join(x.name for x in new)
                           + (" (replacing the AI screens)" if mode == "replace" else "")))
        await store.save_session(state)
        return state


@router.get("/{session_id}/file/{asset_id}")
async def get_file(session_id: str, asset_id: str):
    state = await review._session(session_id)
    for m in state.ui_modules:
        for d in (m.doc, m.revised_doc):
            for sc in (d.screens if d else []):
                if sc.source == "upload" and sc.asset_id == asset_id:
                    path = _asset_path(session_id, sc)
                    if not path.exists():
                        raise HTTPException(404, "file missing")
                    return FileResponse(path, media_type=sc.blocks[0].title,
                                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400"})
    raise HTTPException(404, "file not found")


def _screen(item: UIModule, screen_id: str) -> UIScreen:
    if not item.doc:
        raise HTTPException(404, "screen not found")
    sc = next((x for x in item.doc.screens if x.screen_id == screen_id), None)
    if not sc:
        raise HTTPException(404, "screen not found")
    return sc


@router.post("/{session_id}/screens/update", response_model=SessionState)
async def update_screen(session_id: str, req: ScreenEditRequest):
    state = await review._session(session_id)
    item = review.find(KIND, state, req.item_id)
    _editable(item)
    sc = _screen(item, req.screen_id)
    if req.name is not None and req.name.strip():
        sc.name = req.name.strip()[:80]
    if req.purpose is not None:
        sc.purpose = req.purpose.strip()[:240]
    _touched(item)
    await store.save_session(state)
    return state


@router.post("/{session_id}/screens/move", response_model=SessionState)
async def move_screen(session_id: str, req: ScreenMoveRequest):
    state = await review._session(session_id)
    item = review.find(KIND, state, req.item_id)
    _editable(item)
    sc = _screen(item, req.screen_id)
    lst = item.doc.screens
    i = lst.index(sc)
    j = i + (1 if req.direction > 0 else -1)
    if 0 <= j < len(lst):
        lst[i], lst[j] = lst[j], lst[i]
        _touched(item)
        await store.save_session(state)
    return state


@router.post("/{session_id}/screens/remove", response_model=SessionState)
async def remove_screen(session_id: str, req: ScreenEditRequest):
    state = await review._session(session_id)
    item = review.find(KIND, state, req.item_id)
    _editable(item)
    sc = _screen(item, req.screen_id)
    if len(item.doc.screens) == 1:
        raise HTTPException(400, "a module needs at least one screen — upload or rework before removing the last one")
    item.doc.screens.remove(sc)
    if sc.source == "upload":
        try:
            _asset_path(session_id, sc).unlink(missing_ok=True)
        except OSError:
            pass
    _touched(item)
    await store.save_session(state)
    return state


# ---------------------------------------------------------------- rendering
def _url_asset(session_id: str):
    return lambda fid: f"/api/uiux/{session_id}/file/{fid}"


def _inline_asset(session_id: str, state: SessionState):
    """data: URIs so the downloaded mockup/prototype works offline."""
    index = {sc.asset_id: sc for m in state.ui_modules for sc in (m.doc.screens if m.doc else []) if sc.source == "upload"}

    def f(fid):
        sc = index.get(fid)
        if not sc:
            return ""
        path = _asset_path(session_id, sc)
        if not path.exists():
            return ""
        return f"data:{sc.blocks[0].title};base64," + base64.b64encode(path.read_bytes()).decode()
    return f


@router.get("/{session_id}/render/{ui_id}", response_class=HTMLResponse)
async def render_module(session_id: str, ui_id: str, revised: int = 0):
    state = await review._session(session_id)
    m = review.find(KIND, state, ui_id)
    return HTMLResponse(ui_render.page(state, [m], revised=bool(revised), asset=_url_asset(session_id)))


def _uiux_version(state) -> str:
    v = [b.version for b in state.baselines if b.doc_type == "uiux"]
    return v[-1] if v else "draft"


def mockups_html(state) -> str:
    """Offline mockup file (uploaded designs embedded)."""
    return ui_render.page(state, [m for m in state.ui_modules if m.doc], asset=_inline_asset(state.session_id, state))


def prototype_html(state) -> str:
    """Offline clickable prototype (uploaded designs embedded)."""
    return ui_render.prototype(state, [m for m in state.ui_modules if m.doc], asset=_inline_asset(state.session_id, state))


@router.get("/{session_id}/prototype", response_class=HTMLResponse)
async def prototype(session_id: str, download: int = 0):
    """Clickable prototype of the whole product, in journey order."""
    state = await review._session(session_id)
    if download:
        name = export.file_name(state, "prototype", _uiux_version(state))
        return HTMLResponse(prototype_html(state), headers={"Content-Disposition": f'attachment; filename="{name}"'})
    return HTMLResponse(ui_render.prototype(state, [m for m in state.ui_modules if m.doc], asset=_url_asset(session_id)))


@router.get("/{session_id}/export/mockups.html")
async def export_mockups(session_id: str):
    state = await review._session(session_id)
    if not any(m.doc for m in state.ui_modules):
        raise HTTPException(400, "no screens to export yet")
    name = export.file_name(state, "uiux", _uiux_version(state))
    return HTMLResponse(mockups_html(state), headers={"Content-Disposition": f'attachment; filename="{name}"'})
