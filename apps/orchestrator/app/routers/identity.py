"""
Stage 3 — Identity studio: name + real domain availability, tagline,
colour theme, logo concepts.

2026-09-30 dry-run finding: Identity was a bare 3-swatch picker, and the
"name check" was an LLM writing a *plausible-sounding* availability note
(not a real lookup). This router replaces that with:
  - a real registry lookup per domain (RDAP, falling back to DNS),
  - AI tagline options, AI colour palettes the user can then fine-tune,
  - AI logo concepts returned as sanitized SVG, drawn in the chosen palette.
"""
import asyncio
import json
import logging
import re
import uuid
import xml.etree.ElementTree as ET

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import ai_router, brand, brand_assist, design_import, store
from ..locks import session_lock
from ..models import (
    AssistRequest, BrandOptionsRequest, ChangeOpenRequest, SectionRequest,
    DesignConsentRequest, DesignFileRequest,
    DesignUpdateRequest,
    BlueprintSaveRequest, BlueprintTemplateRequest,
    ChooseRequest, DomainCheck, DomainCheckRequest, LogoChoiceRequest,
    LogoConcept, Palette, PaletteRequest, SessionRequest, SessionState,
)
from .discovery import _clean_line, _extract_json_object

logger = logging.getLogger("phoneme.identity")

router = APIRouter(prefix="/api/identity", tags=["identity"])

# Every combination the user asked to see, available AND taken.
TLDS = ["com", "in", "co.in", "ai", "io", "app"]
COM_PREFIXES = ["get", "try", "use"]
COM_SUFFIXES = ["app", "hq"]

# Authoritative registry RDAP servers, each verified 2026-09-30 to answer
# 200 for a registered name and 404 for an unregistered one. rdap.org is
# only a fallback and its 404 is NOT trusted unless it redirected to a real
# registry (it answers 404 itself for TLDs it doesn't know -- e.g. .io --
# which would falsely read as "available").
RDAP_BASE = {
    "com": "https://rdap.verisign.com/com/v1/domain/",
    "in": "https://rdap.nixiregistry.in/rdap/domain/",
    "co.in": "https://rdap.nixiregistry.in/rdap/domain/",
    "ai": "https://rdap.identitydigital.services/rdap/domain/",
    "io": "https://rdap.identitydigital.services/rdap/domain/",
    "app": "https://pubapi.registry.google/rdap/domain/",
}
RDAP_FALLBACK = "https://rdap.org/domain/"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", ""))


def domain_candidates(name: str) -> list[str]:
    s = _slug(name)
    if not s:
        return []
    out = [f"{s}.{t}" for t in TLDS]
    out += [f"{p}{s}.com" for p in COM_PREFIXES]
    out += [f"{s}{x}.com" for x in COM_SUFFIXES]
    return out


async def _dns_taken(client: httpx.AsyncClient, domain: str) -> bool:
    """DNS can only prove a name is taken (it has NS records); an empty or
    NXDOMAIN answer is not reliable proof it's free, so it never yields
    'available'."""
    try:
        r = await client.get("https://dns.google/resolve", params={"name": domain, "type": "NS"})
        data = r.json()
        return data.get("Status") == 0 and bool(data.get("Answer"))
    except Exception:
        return False


async def check_domain(client: httpx.AsyncClient, domain: str) -> DomainCheck:
    tld = domain.split(".", 1)[1]
    base = RDAP_BASE.get(tld, RDAP_FALLBACK)
    try:
        r = await client.get(base + domain, headers={"Accept": "application/rdap+json"})
        authoritative = base != RDAP_FALLBACK or r.url.host != "rdap.org"
        if r.status_code == 200:
            return DomainCheck(domain=domain, status="taken", method="rdap")
        if r.status_code == 404 and authoritative:
            return DomainCheck(domain=domain, status="available", method="rdap")
    except Exception as exc:
        logger.info("RDAP lookup failed for %s: %s", domain, exc)
    if await _dns_taken(client, domain):
        return DomainCheck(domain=domain, status="taken", method="dns")
    return DomainCheck(domain=domain, status="unknown", method="error")


async def _get(session_id: str) -> SessionState:
    state = await store.get_session(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    return state


def _guard(state: SessionState, keys) -> None:
    """Brand Studio rule: a frozen section (or a frozen Identity without an
    open change request) cannot change."""
    try:
        brand.check_edit(state, keys)
    except ValueError as e:
        raise HTTPException(409, str(e))


def _concept(state: SessionState) -> str:
    return (state.concept_summary or "").strip()


@router.post("/domains", response_model=SessionState)
async def check_domains(req: DomainCheckRequest):
    """Real availability for the name across every TLD/prefix combination,
    plus a short AI note on the name itself (clearly labelled as opinion)."""
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    state = await _get(req.session_id)
    _guard(state, "name")
    domains = domain_candidates(name)
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
        results = await asyncio.gather(*(check_domain(client, d) for d in domains))

    notes = ""
    try:
        r = await ai_router.generate(
            ai_router.Feature.NAME_AVAILABILITY_CHECK,
            f"Product concept: {_concept(state)}\nCandidate name: {name}\n\n"
            "In 2 short sentences: how well does this name fit the concept "
            "(memorable, easy to spell/say, meaning), and any obvious clash "
            "with a well-known existing brand. Do not claim trademark or "
            "domain availability.",
            system="You are a brand-naming reviewer. Plain text, no markdown.",
        )
        notes = _clean_line(r["text"])[:600]
    except Exception as exc:
        logger.info("name note failed: %s", exc)

    state.brand.domains = list(results)
    state.brand.domain_checked_name = name
    state.brand.name_notes = notes
    await store.save_session(state)
    return state


@router.post("/name", response_model=SessionState)
async def choose_name(req: ChooseRequest):
    state = await _get(req.session_id)
    _guard(state, "name")
    name = req.value.strip()
    if not name:
        raise HTTPException(400, "name required")
    if state.selected_name != name:
        # A new name invalidates name-dependent choices made earlier
        # (a frozen logo stays until its section is reopened).
        state.brand.tagline_options = []
        if state.brand.sections.get("logo") != "frozen":
            state.brand.logo_options = []
            state.brand.logo = None
    state.selected_name = name
    await store.save_session(state)
    return state


@router.post("/domain", response_model=SessionState)
async def choose_domain(req: ChooseRequest):
    state = await _get(req.session_id)
    _guard(state, "name")
    state.brand.chosen_domain = req.value.strip() or None
    await store.save_session(state)
    return state


@router.post("/taglines", response_model=SessionState)
async def generate_taglines(req: SessionRequest):
    async with session_lock(req.session_id, "taglines"):
        state = await _get(req.session_id)
        _guard(state, "name")
        if not state.selected_name:
            raise HTTPException(400, "choose a name first")
        r = await ai_router.generate(
            ai_router.Feature.BRAND_IDENTITY,
            f"Product name: {state.selected_name}\nConcept: {_concept(state)}\n\n"
            "Write 6 distinct taglines (max 7 words each) -- mix benefit-led, "
            "playful and confident tones. Respond with ONLY JSON: "
            '{"taglines": ["..."]}',
            system="You are a senior brand copywriter. JSON only.",
        )
        try:
            data = _extract_json_object(r["text"])
            opts = [_clean_line(str(t)).strip('"') for t in data.get("taglines", []) if str(t).strip()]
        except (ValueError, json.JSONDecodeError):
            opts = [_clean_line(l).strip('"') for l in r["text"].splitlines() if l.strip()][:6]
        state.brand.tagline_options = opts[:6]
        await store.save_session(state)
        return state


@router.post("/tagline", response_model=SessionState)
async def choose_tagline(req: ChooseRequest):
    state = await _get(req.session_id)
    _guard(state, "name")
    state.brand.tagline = req.value.strip() or None
    await store.save_session(state)
    return state


HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _palette(d: dict) -> Palette | None:
    try:
        p = Palette(
            name=_clean_line(str(d.get("name", "Palette")))[:40],
            mood=_clean_line(str(d.get("mood", "")))[:80],
            primary=str(d.get("primary", "")).strip(),
            ink=str(d.get("ink", "")).strip(),
            surface=str(d.get("surface", "")).strip(),
            accent=str(d.get("accent", "")).strip(),
            rationale=_clean_line(str(d.get("rationale", "")))[:300],
            **{k: v for k in ("dark_primary", "dark_ink", "dark_surface", "dark_accent")
               if HEX.match(v := str(d.get(k, "")).strip())},
        )
    except Exception:
        return None
    if all(HEX.match(c) for c in (p.primary, p.ink, p.surface, p.accent)):
        return p
    return None


@router.post("/palettes", response_model=SessionState)
async def generate_palettes(req: SessionRequest):
    async with session_lock(req.session_id, "palettes"):
        state = await _get(req.session_id)
        _guard(state, "colours")
        r = await ai_router.generate(
            ai_router.Feature.BRAND_IDENTITY,
            f"Product name: {state.selected_name}\nTagline: {state.brand.tagline or '-'}\n"
            f"Concept: {_concept(state)}\n\n"
            "Propose 3 distinct brand colour palettes for this product. Each "
            "needs: primary (brand colour), ink (near-black text colour), "
            "surface (very light background tint), accent (secondary "
            "highlight). ink on surface must have contrast >= 7:1. Give each "
            "palette its dark theme too: dark_surface (near-black, brand-tinted), "
            "dark_ink (near-white text, >= 7:1 on dark_surface), dark_primary and "
            "dark_accent (the brand colours lifted to read on dark_surface, >= 4.5:1). "
            'Respond with ONLY JSON: {"palettes": [{"name": "...", "mood": "3-4 words", '
            '"primary": "#RRGGBB", "ink": "#RRGGBB", "surface": "#RRGGBB", '
            '"accent": "#RRGGBB", "dark_primary": "#RRGGBB", "dark_ink": "#RRGGBB", '
            '"dark_surface": "#RRGGBB", "dark_accent": "#RRGGBB", "rationale": "one sentence"}]}',
            system="You are a brand designer. JSON only, hex colours only.",
        )
        try:
            data = _extract_json_object(r["text"])
            opts = [p for p in (_palette(x) for x in data.get("palettes", []) if isinstance(x, dict)) if p]
        except (ValueError, json.JSONDecodeError):
            opts = []
        if not opts:
            raise HTTPException(502, "the AI did not return usable palettes — try again")
        state.brand.palette_options = opts[:3]
        design_import.offer_palette(state, apply=False)  # the designs' own palette stays first
        await store.save_session(state)
        return state


@router.post("/palette", response_model=SessionState)
async def choose_palette(req: PaletteRequest):
    state = await _get(req.session_id)
    _guard(state, "colours")
    p = req.palette
    if not all(HEX.match(c) for c in (p.primary, p.ink, p.surface, p.accent)):
        raise HTTPException(400, "palette colours must be #RRGGBB")
    for k in ("dark_primary", "dark_ink", "dark_surface", "dark_accent"):
        v = getattr(p, k)
        if v and not HEX.match(v):
            raise HTTPException(400, "palette colours must be #RRGGBB")
    state.brand.palette = p  # dark fields left empty are derived from the light ones; the logo stays
    state.selected_theme = p.name
    await store.save_session(state)
    return state


# --- SVG sanitising: logos are model-written markup, so treat them as
# untrusted. Only a whitelist of drawing elements/attributes survives, and
# the frontend renders them via <img src="data:..."> (no script execution).
SVG_NS = "http://www.w3.org/2000/svg"
ALLOWED_TAGS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline",
    "polygon", "text", "tspan", "defs", "linearGradient", "radialGradient", "stop",
}
ALLOWED_ATTRS = {
    "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy",
    "r", "rx", "ry", "d", "points", "fill", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity",
    "stroke-opacity", "transform", "font-family", "font-size", "font-weight",
    "letter-spacing", "text-anchor", "dominant-baseline", "id", "offset",
    "stop-color", "stop-opacity", "gradientUnits", "gradientTransform", "fx",
    "fy", "fill-rule", "clip-rule", "xmlns",
}


def sanitize_svg(raw: str) -> str | None:
    m = re.search(r"<svg[\s\S]*?</svg>", raw)
    if not m or len(m.group(0)) > 30000:
        return None
    try:
        root = ET.fromstring(m.group(0))
    except ET.ParseError:
        return None

    def local(tag: str) -> str:
        return tag.split("}", 1)[-1]

    def clean(el: ET.Element) -> bool:
        if local(el.tag) not in ALLOWED_TAGS:
            return False
        for k in list(el.attrib):
            lk = local(k)
            v = el.attrib[k]
            if lk not in ALLOWED_ATTRS or "url(" in v and "url(#" not in v or "javascript" in v.lower():
                del el.attrib[k]
        for child in list(el):
            if not clean(child):
                el.remove(child)
        return True

    if local(root.tag) != "svg" or not clean(root):
        return None
    if not root.tag.startswith("{"):
        root.set("xmlns", SVG_NS)  # a namespaced root already gets xmlns from the serializer
    if "viewBox" not in root.attrib:
        root.set("viewBox", "0 0 240 80")
    ET.register_namespace("", SVG_NS)
    out = ET.tostring(root, encoding="unicode")
    return out


@router.post("/logos", response_model=SessionState)
async def generate_logos(req: SessionRequest):
    async with session_lock(req.session_id, "logos"):
        state = await _get(req.session_id)
        _guard(state, "logo")
        if not state.selected_name or not state.brand.palette:
            raise HTTPException(400, "choose a name and colour theme first")
        p = state.brand.palette
        r = await ai_router.generate(
            ai_router.Feature.BRAND_IDENTITY,
            f"Product name: {state.selected_name}\nTagline: {state.brand.tagline or '-'}\n"
            f"Concept: {_concept(state)}\nPalette: primary {p.primary}, ink {p.ink}, "
            f"surface {p.surface}, accent {p.accent}\n\n"
            "Design 4 distinct logo concepts as compact, hand-written SVG. Each "
            "is a horizontal lockup: a simple geometric icon on the left and "
            "the product name as a wordmark on the right. Rules: viewBox "
            '"0 0 240 80"; only svg, g, path, rect, circle, ellipse, line, '
            "polygon, text, linearGradient/stop; use ONLY the palette colours "
            "(transparent background); text uses font-family "
            "'Manrope, Helvetica, Arial, sans-serif' and font-weight 800; no "
            "images, no scripts, no external references, no style or class "
            "attributes; keep each SVG under 1500 characters. Respond with "
            'ONLY JSON: {"logos": [{"concept": "one-line idea behind the '
            'mark", "svg": "<svg ...>...</svg>"}]}',
            system="You are a logo designer who writes clean, minimal SVG by hand. JSON only.",
        )
        try:
            data = _extract_json_object(r["text"])
            items = data.get("logos", [])
        except (ValueError, json.JSONDecodeError):
            items = [{"concept": "", "svg": s} for s in re.findall(r"<svg[\s\S]*?</svg>", r["text"])]
        logos = []
        for it in items:
            if not isinstance(it, dict):
                continue
            svg = sanitize_svg(str(it.get("svg", "")))
            if svg:
                logos.append(LogoConcept(id=uuid.uuid4().hex[:8], concept=_clean_line(str(it.get("concept", "")))[:160], svg=svg))
        if not logos:
            raise HTTPException(502, "the AI did not return usable logo concepts — try again")
        state.brand.logo_options = logos[:4]
        await store.save_session(state)
        return state


@router.post("/logo", response_model=SessionState)
async def choose_logo(req: LogoChoiceRequest):
    state = await _get(req.session_id)
    _guard(state, "logo")
    logo = next((l for l in state.brand.logo_options if l.id == req.logo_id), None)
    if not logo:
        raise HTTPException(404, "logo concept not found")
    state.brand.logo = logo
    await store.save_session(state)
    return state


# --------------------------------------------------------------------------
# Experience Blueprint (2026-10-07): portal structure + look, frozen with
# the brand so the UI/UX stage draws module screens inside an agreed frame.
# --------------------------------------------------------------------------
@router.get("/blueprint/templates")
async def blueprint_templates():
    from .. import blueprint
    return {"templates": blueprint.catalogue(), "sections": list(blueprint.SECTIONS), "pages": list(blueprint.PAGES),
            "auth_methods": blueprint.AUTH_METHODS, "fonts": list(blueprint.FONTS)}


@router.get("/{session_id}/blueprint/suggest")
async def blueprint_suggest(session_id: str):
    from .. import blueprint
    return {"template_key": blueprint.suggest(await _get(session_id))}


def _editable(state: SessionState, keys=("landing", "web", "mobile")):
    bp = state.brand.blueprint
    if bp and bp.frozen:
        raise HTTPException(409, "the experience blueprint is frozen; unfreeze it to make changes")
    if keys:
        _guard(state, [k for k in keys if brand.applicable(state, k)])


@router.post("/blueprint/template", response_model=SessionState)
async def blueprint_template(req: BlueprintTemplateRequest):
    from .. import blueprint
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        _guard(state, ["theme", "landing", "web", "mobile"])
        _editable(state, keys=())
        try:
            bp = blueprint.from_template(req.template_key, state)
        except KeyError:
            raise HTTPException(404, "unknown template")
        old = state.brand.blueprint
        if old:  # keep the version history, module placement and the owner's designs
            bp.version, bp.module_slots = old.version, old.module_slots
            bp.designs, bp.design_hints, bp.design_files, bp.design_flows = old.designs, old.design_hints, old.design_files, old.design_flows
            bp.landing_copy = old.landing_copy
            if any(a.status != "ignored" for a in old.designs):  # the look was read off the owner's designs: a layout keeps it
                bp.tokens = old.tokens
            design_import.place(bp)
        state.brand.blueprint = bp
        await store.save_session(state)
        return state


@router.post("/blueprint", response_model=SessionState)
async def blueprint_save(req: BlueprintSaveRequest):
    from .. import blueprint
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        _editable(state, keys=())
        bp = blueprint.normalise(req.blueprint)
        old = state.brand.blueprint
        _guard(state, brand.blueprint_sections(old, bp))
        bp.version, bp.frozen, bp.frozen_at = (old.version if old else ""), False, ""
        bp.designs, bp.design_hints, bp.design_files, bp.design_flows = (old.designs, old.design_hints, old.design_files, old.design_flows) if old else ([], bp.design_hints, [], [])  # server-managed
        design_import.place(bp)
        state.brand.blueprint = bp
        await store.save_session(state)
        return state


@router.post("/blueprint/freeze", response_model=SessionState)
async def blueprint_freeze(req: SessionRequest):
    from .. import blueprint
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        bp = state.brand.blueprint
        if not bp:
            raise HTTPException(400, "choose a template first")
        if bp.frozen:
            return state
        err = design_import.identity_gate(state)
        if err:
            raise HTTPException(409, err)
        state.brand.blueprint = blueprint.freeze(blueprint.normalise(bp), bp.version)
        await store.save_session(state)
        return state


@router.post("/blueprint/unfreeze", response_model=SessionState)
async def blueprint_unfreeze(req: SessionRequest):
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        bp = state.brand.blueprint
        if not bp or not bp.frozen:
            raise HTTPException(400, "the blueprint is not frozen")
        bp.frozen = False  # version kept: the next freeze becomes x.(n+1)
        await store.save_session(state)
        return state


@router.get("/{session_id}/blueprint/preview")
async def blueprint_preview(session_id: str):
    from fastapi.responses import HTMLResponse
    from .. import blueprint, ui_render
    state = await _get(session_id)
    bp = state.brand.blueprint
    if not bp:
        raise HTTPException(404, "no blueprint yet")
    mods, nav = blueprint.preview_modules(state, bp)
    html = ui_render.prototype(state, mods, nav=nav, title="experience blueprint preview",
                               asset=lambda fid: f"/api/identity/{session_id}/designs/file/{fid}")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- the owner's own designs
@router.post("/{session_id}/designs", response_model=SessionState)
async def designs_upload(session_id: str, files: list[UploadFile] = File(...)):
    """One upload for every design: boards are split into screens, every
    screen is read by AI in the background and placed in the frame."""
    from .. import blueprint
    async with session_lock(session_id, "blueprint"):
        state = await _get(session_id)
        _editable(state)
        if state.design_import.status == "running":
            raise HTTPException(409, "still reading your last upload — wait a moment")
        if len(files) > design_import.MAX_FILES:
            raise HTTPException(400, f"upload at most {design_import.MAX_FILES} files at a time (a zip counts as one)")
        got = []
        for f in files:
            data = await f.read(design_import.MAX_BYTES + 1)
            if len(data) > design_import.MAX_BYTES:
                raise HTTPException(413, f"{f.filename}: larger than {design_import.MAX_BYTES // (1024 * 1024)} MB")
            got.append((f.filename or "design.png", data))
        if not state.brand.blueprint:
            state.brand.blueprint = blueprint.from_template(blueprint.suggest(state), state)
            await store.save_session(state)
        try:
            await design_import.start(session_id, got)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return await _get(session_id)


@router.get("/{session_id}/designs/file/{design_id}")
async def designs_file(session_id: str, design_id: str):
    from fastapi.responses import FileResponse
    try:
        p = design_import.path_of(session_id, design_id)
    except ValueError:
        raise HTTPException(400, "bad id")
    if not p.exists():
        raise HTTPException(404, "design not found")
    return FileResponse(p, media_type="image/png", headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400"})


@router.get("/{session_id}/designs/coverage")
async def designs_coverage(session_id: str):
    return design_import.coverage(await _get(session_id))


@router.post("/designs/consent", response_model=SessionState)
async def designs_consent(req: DesignConsentRequest):
    """The owner agrees (or withdraws) that empty places in the frame are generated in their style."""
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        bp = state.brand.blueprint
        if not bp:
            raise HTTPException(400, "choose a template first")
        if bp.frozen:
            raise HTTPException(409, "unfreeze the blueprint to change it")
        _guard(state, [k for k in ("landing", "web", "mobile") if brand.applicable(state, k)])
        bp.design_hints.generate_ok = bool(req.ok)
        await store.save_session(state)
        return state


@router.post("/designs/update", response_model=SessionState)
async def designs_update(req: DesignUpdateRequest):
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        _editable(state)
        try:
            design_import.update(state, req)
        except KeyError:
            raise HTTPException(404, "design not found")
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        await store.save_session(state)
        return state


@router.post("/designs/use-colours", response_model=SessionState)
async def designs_use_colours(req: SessionRequest):
    """Switch the brand colours to the ones read off the owner's designs."""
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        _guard(state, "colours")
        p = design_palette_or_404(state)
        state.brand.palette = p
        state.selected_theme = p.name
        design_import.offer_palette(state)
        state.brand.palette = p
        await store.save_session(state)
        return state


def design_palette_or_404(state):
    p = design_import.design_palette(state)
    if not p:
        raise HTTPException(400, "no colours were read from your designs")
    return p


@router.post("/designs/refill", response_model=SessionState)
async def designs_refill(req: SessionRequest):
    """Use what was read off the designs again (after trying a starting point)."""
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        _guard(state, ["theme", "landing", "web", "mobile"])
        _editable(state, keys=())
        try:
            design_import.refill(state)
        except ValueError as e:
            raise HTTPException(400, str(e))
        await store.save_session(state)
        return state


@router.post("/assist", response_model=SessionState)
async def assist(req: AssistRequest):
    """Ask AI to change one Brand Studio section in plain words."""
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        try:
            await brand_assist.ask(state, req.section, req.message)
        except ValueError as e:
            raise HTTPException(409 if "frozen" in str(e) or "change request" in str(e) else 400, str(e))
        await store.save_session(state)
        return state


@router.post("/assist/undo", response_model=SessionState)
async def assist_undo(req: AssistRequest):
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        try:
            brand_assist.undo(state, req.section)
        except ValueError as e:
            raise HTTPException(409, str(e))
        await store.save_session(state)
        return state


@router.get("/{session_id}/designs/files")
async def designs_files(session_id: str):
    state = await _get(session_id)
    return {"folder": f"{state.selected_name or 'Product'} / Designs", "files": design_import.files_view(state)}


@router.get("/{session_id}/designs/source/{file_id}")
async def designs_source(session_id: str, file_id: str):
    from fastapi.responses import FileResponse
    state = await _get(session_id)
    bp = state.brand.blueprint
    f = next((x for x in (bp.design_files if bp else []) if x.file_id == file_id), None)
    if not f:
        raise HTTPException(404, "file not found")
    path = design_import.source_path(session_id, f)
    if not path.exists():
        raise HTTPException(404, "file missing")
    mime = {"zip": "application/zip", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}.get(f.ext, "image/png")
    safe = re.sub(r'[^A-Za-z0-9._ -]+', "_", f.name) or f"design.{f.ext}"
    return FileResponse(path, media_type=mime, filename=safe, headers={"X-Content-Type-Options": "nosniff"})


@router.post("/designs/files/remove", response_model=SessionState)
async def designs_file_remove(req: DesignFileRequest):
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        _editable(state)
        if state.design_import.status == "running":
            raise HTTPException(409, "still reading your last upload — wait a moment")
        try:
            design_import.remove_file(state, req.file_id)
        except KeyError:
            raise HTTPException(404, "file not found")
        await store.save_session(state)
        return state


@router.post("/designs/files/reread", response_model=SessionState)
async def designs_file_reread(req: DesignFileRequest):
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        _editable(state)
        if state.design_import.status == "running":
            raise HTTPException(409, "still reading your last upload — wait a moment")
        try:
            await design_import.reread_file(req.session_id, req.file_id)
        except KeyError:
            raise HTTPException(404, "file not found")
        return await _get(req.session_id)


@router.post("/complete", response_model=SessionState)
async def complete_identity(req: SessionRequest):
    """Freeze Identity: every section at once (v1.0), or -- with a change
    request open -- approve it as the next version."""
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        if brand.frozen(state):
            return state
        try:
            brand.freeze_identity(state, design_import.identity_gate)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if state.stage == "identity":
            state.stage = "freeze"
        await store.save_session(state)
        return state


# ---------------------------------------------------------------- Brand Studio (2026-10-13)
@router.get("/{session_id}/brand")
async def brand_status(session_id: str):
    state = await _get(session_id)
    b = state.brand
    return {"sections": brand.status(state), "frozen": brand.frozen(state), "version": b.version or ("1.0" if b.completed else ""),
            "change": b.change.model_dump(exclude={"before"}) if b.change else None,
            "impacts": brand.impacts(state) if b.completed else [],
            "history": [h.model_dump() for h in b.history], "standard_pages": brand.STANDARD_PAGES,
            "dark": brand.dark_of(b.palette) if b.palette else None}


@router.post("/section", response_model=SessionState)
async def brand_section(req: SectionRequest):
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        try:
            brand.set_section(state, req.key, req.action)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(409, str(e))
        await store.save_session(state)
        return state


@router.post("/change/open", response_model=SessionState)
async def change_open(req: ChangeOpenRequest):
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        try:
            brand.open_change(state, req.sections, req.reason)
        except ValueError as e:
            raise HTTPException(409, str(e))
        await store.save_session(state)
        return state


@router.post("/change/cancel", response_model=SessionState)
async def change_cancel(req: SessionRequest):
    async with session_lock(req.session_id, "blueprint"):
        state = await _get(req.session_id)
        try:
            brand.cancel_change(state)
        except ValueError as e:
            raise HTTPException(409, str(e))
        await store.save_session(state)
        return state


@router.post("/options", response_model=SessionState)
async def brand_options(req: BrandOptionsRequest):
    state = await _get(req.session_id)
    b = state.brand
    if req.favicon_style is not None or req.favicon_letter is not None:
        _guard(state, "logo")
        if req.favicon_style in ("monogram", "logo"):
            b.favicon_style = req.favicon_style
        if req.favicon_letter is not None:
            b.favicon_letter = re.sub(r"[<>&\"]", "", req.favicon_letter.strip())[:2]
    if req.logo_placement is not None:
        _guard(state, "theme")
        if req.logo_placement not in ("left", "center"):
            raise HTTPException(400, "logo placement is left or center")
        b.logo_placement = req.logo_placement
    await store.save_session(state)
    return state


@router.get("/{session_id}/favicon.svg")
async def favicon(session_id: str):
    from fastapi.responses import Response
    state = await _get(session_id)
    return Response(brand.favicon_svg(state), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
