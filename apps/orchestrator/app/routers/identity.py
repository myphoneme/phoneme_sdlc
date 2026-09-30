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
from fastapi import APIRouter, HTTPException

from .. import ai_router, store
from ..locks import session_lock
from ..models import (
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
    name = req.value.strip()
    if not name:
        raise HTTPException(400, "name required")
    if state.selected_name != name:
        # A new name invalidates name-dependent choices made earlier.
        state.brand.tagline_options = []
        state.brand.logo_options = []
        state.brand.logo = None
    state.selected_name = name
    await store.save_session(state)
    return state


@router.post("/domain", response_model=SessionState)
async def choose_domain(req: ChooseRequest):
    state = await _get(req.session_id)
    state.brand.chosen_domain = req.value.strip() or None
    await store.save_session(state)
    return state


@router.post("/taglines", response_model=SessionState)
async def generate_taglines(req: SessionRequest):
    async with session_lock(req.session_id, "taglines"):
        state = await _get(req.session_id)
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
        r = await ai_router.generate(
            ai_router.Feature.BRAND_IDENTITY,
            f"Product name: {state.selected_name}\nTagline: {state.brand.tagline or '-'}\n"
            f"Concept: {_concept(state)}\n\n"
            "Propose 3 distinct brand colour palettes for this product. Each "
            "needs: primary (brand colour), ink (near-black text colour), "
            "surface (very light background tint), accent (secondary "
            "highlight). ink on surface must have contrast >= 7:1. Respond "
            'with ONLY JSON: {"palettes": [{"name": "...", "mood": "3-4 words", '
            '"primary": "#RRGGBB", "ink": "#RRGGBB", "surface": "#RRGGBB", '
            '"accent": "#RRGGBB", "rationale": "one sentence"}]}',
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
        await store.save_session(state)
        return state


@router.post("/palette", response_model=SessionState)
async def choose_palette(req: PaletteRequest):
    state = await _get(req.session_id)
    p = req.palette
    if not all(HEX.match(c) for c in (p.primary, p.ink, p.surface, p.accent)):
        raise HTTPException(400, "palette colours must be #RRGGBB")
    if state.brand.palette != p:
        state.brand.logo_options = []  # logos are drawn in the palette
        state.brand.logo = None
    state.brand.palette = p
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
    root.set("xmlns", SVG_NS)
    if "viewBox" not in root.attrib:
        root.set("viewBox", "0 0 240 80")
    ET.register_namespace("", SVG_NS)
    out = ET.tostring(root, encoding="unicode")
    return out


@router.post("/logos", response_model=SessionState)
async def generate_logos(req: SessionRequest):
    async with session_lock(req.session_id, "logos"):
        state = await _get(req.session_id)
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
    logo = next((l for l in state.brand.logo_options if l.id == req.logo_id), None)
    if not logo:
        raise HTTPException(404, "logo concept not found")
    state.brand.logo = logo
    await store.save_session(state)
    return state


@router.post("/complete", response_model=SessionState)
async def complete_identity(req: SessionRequest):
    state = await _get(req.session_id)
    missing = [
        label for label, ok in (
            ("name", state.selected_name), ("tagline", state.brand.tagline),
            ("colour theme", state.brand.palette), ("logo", state.brand.logo),
        ) if not ok
    ]
    if missing:
        raise HTTPException(400, "still to choose: " + ", ".join(missing))
    state.brand.completed = True
    if state.stage == "identity":
        state.stage = "freeze"
    await store.save_session(state)
    return state
