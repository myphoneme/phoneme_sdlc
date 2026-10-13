"""
Brand Studio (2026-10-13) -- the Identity stage as seven sections that stay
editable on the fly:

    1 name      Name & brand (name, domain, tagline)
    2 colours   Colour theme, light and dark
    3 logo      Logo & favicon
    4 theme     Brand theme (type, corners, spacing, platforms) + the standard
                modules, which only inherit colours and logo placement
    5 landing   Marketing landing page
    6 web       Web pages theme catalogue
    7 mobile    Mobile pages theme

Rules (Anuj, 2026-10-13): while Identity is open, sections change freely and
can be frozen one by one with no version change. Freezing Identity freezes
all seven as v1.0. After that every change is a change request: the chosen
sections reopen, the impact on later stages is listed, and approving it
re-freezes Identity as the next version -- UI/UX and UX flow, which are drawn
in the brand, then need re-approval (review.BRAND_KEY).
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .models import IdentityChange, IdentityVersion

SECTIONS = [
    ("name", "Name & brand"), ("colours", "Colour theme"), ("logo", "Logo & favicon"), ("theme", "Brand theme"),
    ("landing", "Marketing landing page"), ("web", "Web pages theme"), ("mobile", "Mobile pages theme"),
]
LABEL = dict(SECTIONS)
BLUEPRINT_FIELDS = {
    "theme": ("template_key", "platforms", "primary", "tokens", "auth", "notes"),
    "landing": ("landing_sections", "public_pages", "public_features"),
    "web": ("web",),
    "mobile": ("mobile",),
}
STANDARD_PAGES = ["Sign in", "Create account", "Forgot password", "Change password", "Profile & settings", "Admin & roles"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ section state
def applicable(state, key: str) -> bool:
    bp = state.brand.blueprint
    if key == "web":
        return not bp or bp.platforms != "mobile"
    if key == "mobile":
        return not bp or bp.platforms != "web"
    return True


def missing(state, key: str) -> str | None:
    b, bp = state.brand, state.brand.blueprint
    if key == "name":
        return None if state.selected_name and b.tagline else ("choose a name" if not state.selected_name else "choose a tagline")
    if key == "colours":
        return None if b.palette else "choose a colour theme"
    if key == "logo":
        return None if b.logo else "choose a logo"
    if not bp:
        return "choose a starting point for the brand theme"
    if key == "landing" and not bp.landing_sections:
        return "add at least the hero section"
    if key == "mobile" and not bp.mobile.tabs:
        return "name the phone tabs"
    return None


def status(state) -> list[dict]:
    b = state.brand
    out = []
    for key, label in SECTIONS:
        if not applicable(state, key):
            st = "na"
        elif b.sections.get(key) == "frozen" or (b.completed and not (b.change and key in b.change.sections)):
            st = "frozen"
        else:
            st = "todo" if missing(state, key) else "ready"
        out.append({"key": key, "label": label, "status": st, "missing": missing(state, key) or "",
                    "in_change": bool(b.change and key in b.change.sections)})
    return out


def frozen(state) -> bool:
    """Identity as a whole is frozen (and no change request is open)."""
    return bool(state.brand.completed and not state.brand.change)


def check_edit(state, keys) -> None:
    """Raise ValueError when any of these sections may not change now."""
    b = state.brand
    for key in ([keys] if isinstance(keys, str) else keys):
        if b.completed and not b.change:
            raise ValueError(f"Identity is frozen (v{b.version or '1.0'}) — open a change request to change {LABEL[key]}")
        if b.completed and b.change and key not in b.change.sections:
            raise ValueError(f"{LABEL[key]} is not part of the open change request — add it to the request first")
        if b.sections.get(key) == "frozen":
            raise ValueError(f"{LABEL[key]} is frozen — unfreeze it to change it")


def blueprint_sections(old, new) -> list[str]:
    """Which sections a blueprint save touches."""
    if old is None:
        return ["theme", "landing", "web", "mobile"]
    a, n = old.model_dump(), new.model_dump()
    return [k for k, fields in BLUEPRINT_FIELDS.items() if any(a.get(f) != n.get(f) for f in fields)]


def set_section(state, key: str, action: str) -> None:
    if key not in LABEL:
        raise KeyError("unknown section")
    b = state.brand
    if action == "freeze":
        if b.completed and not b.change:
            raise ValueError("Identity is already frozen")
        m = missing(state, key) if applicable(state, key) else None
        if m:
            raise ValueError(f"{LABEL[key]}: {m}")
        b.sections[key] = "frozen"
    elif action == "unfreeze":
        if b.completed and not b.change:
            raise ValueError(f"Identity is frozen (v{b.version or '1.0'}) — open a change request to change {LABEL[key]}")
        if b.completed and b.change and key not in b.change.sections:
            raise ValueError(f"{LABEL[key]} is not part of the open change request")
        b.sections.pop(key, None)
        if key in BLUEPRINT_FIELDS and b.blueprint:
            b.blueprint.frozen = False
    else:
        raise ValueError("action is freeze or unfreeze")


# ------------------------------------------------------------------ freezing Identity / change requests
def impacts(state) -> list[str]:
    out = []
    for dt, label in (("uiux", "UI/UX Design"), ("uxflow", "UX Flow & Design Spec")):
        bs = [x for x in state.baselines if x.doc_type == dt]
        if bs:
            out.append(f"{label} v{bs[-1].version} is drawn in the brand — it must be re-approved and re-baselined")
    if any(m.doc for m in state.ui_modules) and not any(x.doc_type == "uiux" for x in state.baselines):
        out.append("UI/UX screens in progress pick up the new brand automatically")
    if state.stage not in ("discovery", "confirm", "research", "identity"):
        out.append("Scope, BRD/PRD and Technical Design are not affected")
    return out or ["Nothing has been built on this Identity yet"]


def freeze_identity(state, gate) -> None:
    """Freeze every section and Identity itself (v1.0, or the next version
    when a change request is approved). `gate` is design_import.identity_gate."""
    from . import blueprint as bpmod
    b = state.brand
    todo = [f"{LABEL[k]} ({missing(state, k)})" for k, _ in SECTIONS if applicable(state, k) and missing(state, k)]
    if todo:
        raise ValueError("still to choose: " + ", ".join(todo))
    err = gate(state)
    if err:
        raise ValueError(err)
    for k, _ in SECTIONS:
        if applicable(state, k):
            b.sections[k] = "frozen"
        else:
            b.sections.pop(k, None)
    if not b.blueprint.frozen:
        b.blueprint = bpmod.freeze(bpmod.normalise(b.blueprint), b.blueprint.version)
    if b.change:
        major, _, minor = (b.version or "1.0").partition(".")
        b.version = f"{major}.{int(minor or 0) + 1}"
        summary = "Change request: " + ", ".join(LABEL[k] for k in b.change.sections) + (f" — {b.change.reason}" if b.change.reason else "")
        b.change = None
    else:
        b.version = b.version or "1.0"
        summary = "Identity frozen"
    b.frozen_at = _now()
    b.history.append(IdentityVersion(version=b.version, at=b.frozen_at, summary=summary))
    b.completed = True


def open_change(state, keys: list[str], reason: str) -> None:
    b = state.brand
    if not b.completed:
        raise ValueError("Identity is not frozen — change sections directly")
    keys = [k for k in dict.fromkeys(keys) if k in LABEL]
    if not keys:
        raise ValueError("choose the sections to change")
    if b.change:  # add sections to the open request
        for k in keys:
            if k not in b.change.sections:
                b.change.sections.append(k)
    else:
        b.version = b.version or "1.0"
        b.change = IdentityChange(sections=keys, reason=reason.strip()[:300], opened_at=_now(), impacts=impacts(state),
                                  before={"brand": b.model_dump(exclude={"change", "history"}),
                                          "selected_name": state.selected_name, "selected_theme": state.selected_theme})
    for k in keys:
        b.sections.pop(k, None)
        if k in BLUEPRINT_FIELDS and b.blueprint:
            b.blueprint.frozen = False


def cancel_change(state) -> None:
    from .models import BrandIdentity
    b = state.brand
    if not b.change:
        raise ValueError("no change request is open")
    before = b.change.before
    hist = b.history
    state.brand = BrandIdentity(**before["brand"])
    state.brand.history = hist
    state.selected_name = before.get("selected_name")
    state.selected_theme = before.get("selected_theme")


# ------------------------------------------------------------------ dark theme
def _rgb(h: str):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _hex(c) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02X}" for v in c)


def _mix(a: str, b: str, t: float) -> str:
    x, y = _rgb(a), _rgb(b)
    return _hex([x[i] * (1 - t) + y[i] * t for i in range(3)])


def _lum(h: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def _readable_on(colour: str, bg: str, target: float = 4.5) -> str:
    c = colour
    for i in range(1, 11):
        if contrast(c, bg) >= target:
            return c
        c = _mix(colour, "#FFFFFF", i * 0.09)
    return c


def dark_of(p) -> dict:
    """The dark theme of a palette: the owner's own values where set,
    otherwise derived (a near-black tinted with the brand, light text, and
    brand colours lifted until they read on it)."""
    surf = p.dark_surface or _mix("#121214", p.primary, 0.07)
    return {
        "primary": p.dark_primary or _readable_on(p.primary, surf),
        "ink": p.dark_ink or _mix("#F1F1F3", p.primary, 0.04),
        "surface": surf,
        "accent": p.dark_accent or _readable_on(p.accent, surf, 3.0),
    }


def with_dark(p):
    """Palette with every dark field filled in (stored as derived values are
    shown to the owner, who may then edit them)."""
    d = dark_of(p)
    return p.model_copy(update={f"dark_{k}": v for k, v in d.items()})


# ------------------------------------------------------------------ favicon
def favicon_svg(state) -> str:
    b = state.brand
    p = b.palette
    primary, surface = (p.primary, p.surface) if p else ("#FF7200", "#FFF7F0")
    font = b.blueprint.tokens.heading_font if b.blueprint else "Manrope"
    if b.favicon_style == "logo" and b.logo:
        try:
            ET.register_namespace("", "http://www.w3.org/2000/svg")
            n = iter(range(99))
            svg = re.sub(r'\sxmlns="[^"]*"', lambda m: m.group(0) if next(n) == 0 else "", b.logo.svg)
            root = ET.fromstring(svg)
            vb = root.get("viewBox", "0 0 240 80")
            inner = "".join(ET.tostring(c, encoding="unicode") for c in root)
            return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
                    f'<rect width="64" height="64" rx="14" fill="{surface}"/>'
                    f'<svg x="4" y="4" width="56" height="56" viewBox="{vb}" preserveAspectRatio="xMidYMid meet">{inner}</svg></svg>')
        except ET.ParseError:
            pass
    letter = (b.favicon_letter or (state.selected_name or "?")[:1]).strip()[:2] or "?"
    fg = "#FFFFFF" if contrast("#FFFFFF", primary) >= contrast("#111111", primary) else "#111111"
    size = 38 if len(letter) == 1 else 28
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="14" fill="{primary}"/>'
            f'<text x="32" y="33" text-anchor="middle" dominant-baseline="central" font-family="{font}, system-ui, sans-serif" '
            f'font-weight="800" font-size="{size}" fill="{fg}">{_esc(letter)}</text></svg>')


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
