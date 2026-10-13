"""
Brand Studio AI assistant (2026-10-13): every section has an "Ask AI" chat.
The owner says what to change in plain words; the AI answers and proposes
changes limited to that section, which are validated, applied through the
same rules as a manual edit (frozen sections and change requests are
respected) and can be undone.
"""
import json
import re
from datetime import datetime, timezone

from . import ai_router, blueprint, brand, reqdoc
from .models import Palette

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_THREAD = 24

SCHEMA = {
    "name": '{"tagline": "<max 80 chars>"}',
    "colours": '{"palette": {"primary": "#RRGGBB", "ink": "#RRGGBB", "surface": "#RRGGBB", "accent": "#RRGGBB", '
               '"dark_primary": "#RRGGBB", "dark_ink": "#RRGGBB", "dark_surface": "#RRGGBB", "dark_accent": "#RRGGBB"}} (any subset)',
    "logo": '{"favicon_style": "monogram|logo", "favicon_letter": "<1-2 letters>"}',
    "theme": '{"tokens": {"heading_font": "<font>", "body_font": "<font>", "radius": "sharp|rounded|soft", "density": "comfortable|compact"}, '
             '"platforms": "web|mobile|both", "primary": "web|mobile", "auth_methods": ["email_password|email_otp|mobile_otp|google|apple|sso"], '
             '"logo_placement": "left|center"} (any subset)',
    "landing": '{"landing_sections": ["hero", "promise|features|download|pricing|faq|cta in order"], "public_pages": ["Pricing|About|Blog|Contact|Download app"], '
               '"public_features": "<text>", "copy": {"<section>": {"title": "...", "text": "...", "items": ["..."]}}} (any subset)',
    "web": '{"nav": "sidebar|top", "home": "dashboard|feed|inbox", "notes": "<notes for designers>"}',
    "mobile": '{"tabs": ["<up to 5 tab names>"], "share_target": true, "push": true, "offline": true} (any subset)',
    "standard": '{"logo_placement": "left|center", "auth_methods": ["..."]}',
}
SECTION_KEY = {"standard": "theme", "designs": "landing"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def current(state, section: str) -> dict:
    b, bp = state.brand, state.brand.blueprint
    if section == "name":
        return {"name": state.selected_name, "tagline": b.tagline, "domain": b.chosen_domain}
    if section == "colours":
        return {"palette": b.palette.model_dump(exclude={"rationale"}) if b.palette else None}
    if section == "logo":
        return {"logo_concept": b.logo.concept if b.logo else None, "favicon_style": b.favicon_style, "favicon_letter": b.favicon_letter}
    if not bp:
        return {}
    if section in ("theme", "standard"):
        return {"tokens": bp.tokens.model_dump(), "platforms": bp.platforms, "primary": bp.primary,
                "auth_methods": bp.auth.methods, "logo_placement": b.logo_placement}
    if section == "landing":
        return {"landing_sections": bp.landing_sections, "public_pages": bp.public_pages,
                "public_features": bp.public_features, "copy": bp.landing_copy}
    if section == "web":
        return {"nav": bp.web.nav, "home": bp.web.home, "notes": bp.notes}
    if section == "mobile":
        return {"tabs": bp.mobile.tabs, "share_target": bp.mobile.share_target, "push": bp.mobile.push, "offline": bp.mobile.offline}
    return {}


def snapshot(state) -> dict:
    b = state.brand
    return {"tagline": b.tagline, "palette": b.palette.model_dump() if b.palette else None,
            "favicon_style": b.favicon_style, "favicon_letter": b.favicon_letter, "logo_placement": b.logo_placement,
            "blueprint": b.blueprint.model_dump(exclude={"designs", "design_files", "design_flows", "design_hints"}) if b.blueprint else None}


def restore(state, snap: dict) -> None:
    from .models import ExperienceBlueprint
    b = state.brand
    b.tagline = snap.get("tagline")
    b.palette = Palette(**snap["palette"]) if snap.get("palette") else None
    b.favicon_style, b.favicon_letter, b.logo_placement = snap.get("favicon_style", "monogram"), snap.get("favicon_letter", ""), snap.get("logo_placement", "left")
    if snap.get("blueprint") and b.blueprint:
        keep = {"designs": b.blueprint.designs, "design_files": b.blueprint.design_files, "design_flows": b.blueprint.design_flows, "design_hints": b.blueprint.design_hints}
        b.blueprint = ExperienceBlueprint(**snap["blueprint"], **keep)


def apply(state, section: str, ch: dict) -> list[str]:
    """Validate and apply the AI's proposed changes; returns what changed."""
    b, bp = state.brand, state.brand.blueprint
    done = []
    if not isinstance(ch, dict):
        return done
    if section == "name" and isinstance(ch.get("tagline"), str) and ch["tagline"].strip():
        b.tagline = ch["tagline"].strip()[:80]
        done.append(f"Tagline: “{b.tagline}”")
    if section == "colours" and isinstance(ch.get("palette"), dict):
        base = (b.palette or Palette()).model_dump()
        upd = {k: v.upper() for k, v in ch["palette"].items() if k in ("primary", "ink", "surface", "accent", "dark_primary", "dark_ink", "dark_surface", "dark_accent")
               and isinstance(v, str) and HEX.match(v)}
        if upd:
            name = base.get("name") or "Palette"
            base.update(upd, name=name if name.endswith(" (edited)") else f"{name} (edited)")
            b.palette = Palette(**base)
            done.append("Colours: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in upd.items()))
    if section == "logo":
        if ch.get("favicon_style") in ("monogram", "logo"):
            b.favicon_style = ch["favicon_style"]
            done.append(f"Favicon: {b.favicon_style}")
        if isinstance(ch.get("favicon_letter"), str) and ch["favicon_letter"].strip():
            b.favicon_letter = re.sub(r"[<>&\"]", "", ch["favicon_letter"].strip())[:2]
            done.append(f"Favicon letters: {b.favicon_letter}")
    if section in ("theme", "standard") and ch.get("logo_placement") in ("left", "center"):
        b.logo_placement = ch["logo_placement"]
        done.append(f"Logo placement: {b.logo_placement}")
    if bp and section in ("theme", "standard", "landing", "web", "mobile"):
        x = bp.model_copy(deep=True)
        if section == "theme":
            t = ch.get("tokens") if isinstance(ch.get("tokens"), dict) else {}
            for k in ("heading_font", "body_font", "radius", "density"):
                if isinstance(t.get(k), str):
                    setattr(x.tokens, k, t[k])
            if ch.get("platforms") in blueprint.PLATFORMS:
                x.platforms = ch["platforms"]
            if ch.get("primary") in ("web", "mobile"):
                x.primary = ch["primary"]
        if section in ("theme", "standard") and isinstance(ch.get("auth_methods"), list):
            x.auth.methods = [m for m in ch["auth_methods"] if m in blueprint.AUTH_METHODS] or x.auth.methods
        if section == "landing":
            if isinstance(ch.get("landing_sections"), list):
                x.landing_sections = [str(s) for s in ch["landing_sections"]]
            if isinstance(ch.get("public_pages"), list):
                x.public_pages = ["Landing"] + [str(p) for p in ch["public_pages"]]
            if isinstance(ch.get("public_features"), str):
                x.public_features = ch["public_features"]
            if isinstance(ch.get("copy"), dict):
                x.landing_copy = {**x.landing_copy, **blueprint.clean_copy(ch["copy"])}
        if section == "web":
            if ch.get("nav") in blueprint.NAVS:
                x.web.nav = ch["nav"]
            if ch.get("home") in blueprint.HOMES:
                x.web.home = ch["home"]
            if isinstance(ch.get("notes"), str):
                x.notes = ch["notes"]
        if section == "mobile":
            if isinstance(ch.get("tabs"), list):
                x.mobile.tabs = [str(t) for t in ch["tabs"]]
            for k in ("share_target", "push", "offline"):
                if isinstance(ch.get(k), bool):
                    setattr(x.mobile, k, ch[k])
        x = blueprint.normalise(x)
        before, after = bp.model_dump(), x.model_dump()
        diff = [k for k in after if before.get(k) != after.get(k) and k not in ("designs", "design_files", "design_flows", "design_hints")]
        if diff:
            state.brand.blueprint = x
            from . import design_import
            design_import.place(x)
            label = {"tokens": "Type & corners", "platforms": "Where it runs", "primary": "Which comes first", "auth": "Sign-in",
                     "landing_sections": "Landing sections", "public_pages": "Public pages", "public_features": "Public features",
                     "landing_copy": "Landing text", "web": "Web app frame", "notes": "Designer notes", "mobile": "Phone app"}
            done.append("Changed: " + ", ".join(label.get(k, k) for k in diff))
    return done


async def ask(state, section: str, message: str) -> dict:
    if section not in SCHEMA:
        raise ValueError("this section has no assistant")
    message = message.strip()[:1200]
    if not message:
        raise ValueError("write what you would like to change")
    brand.check_edit(state, SECTION_KEY.get(section, section) if section != "standard" else "theme")
    thread = state.brand.assist.setdefault(section, [])
    history = "\n".join(f"{m['role']}: {m['text']}" for m in thread[-8:])
    bp = state.brand.blueprint
    hints = bp.design_hints.summary if bp else ""
    prompt = (
        f"Product: {state.selected_name} — {state.brand.tagline or ''}\nConcept: {(state.concept_summary or '')[:600]}\n"
        + (f"The owner uploaded designs: {hints}\n" if hints else "")
        + f"\nBrand Studio section: {brand.LABEL.get(section, 'Standard modules')}\n"
        f"Current values: {json.dumps(current(state, section), ensure_ascii=False)}\n"
        + (f"Fonts available: {', '.join(blueprint.FONTS)}\n" if section == "theme" else "")
        + (f"\nConversation so far:\n{history}\n" if history else "")
        + f"\nOwner: {message}\n\n"
        "You are the brand designer helping in this section only. Answer briefly and concretely in plain language. "
        "If the owner asks for a change, include it in \"changes\" using exactly this shape (leave out what does not change): "
        f"{SCHEMA[section]}. Keep text readable (contrast at least 4.5:1). "
        'Respond with ONLY JSON: {"reply": "<2-4 sentences>", "changes": {}}'
    )
    r = await ai_router.generate(ai_router.Feature.BRAND_IDENTITY, prompt,
                                 system="You are a senior brand and product designer inside a design tool. JSON only.")
    try:
        d = reqdoc._extract_json(r["text"])
    except Exception:  # noqa: BLE001
        d = {"reply": str(r.get("text") or "")[:600], "changes": {}}
    if not isinstance(d, dict):
        d = {"reply": "", "changes": {}}
    snap = snapshot(state)
    done = apply(state, section, d.get("changes") or {})
    reply = str(d.get("reply") or "").strip()[:800] or ("Done." if done else "I could not work out a change from that — could you say it another way?")
    thread.append({"role": "owner", "text": message, "at": _now()})
    thread.append({"role": "ai", "text": reply, "at": _now(), "applied": done, "undo": snap if done else None})
    del thread[:-MAX_THREAD]
    return {"reply": reply, "applied": done}


def undo(state, section: str) -> list[str]:
    brand.check_edit(state, SECTION_KEY.get(section, section) if section != "standard" else "theme")
    thread = state.brand.assist.get(section) or []
    last = next((m for m in reversed(thread) if m.get("role") == "ai" and m.get("undo")), None)
    if not last:
        raise ValueError("nothing to undo")
    restore(state, last["undo"])
    applied = last.get("applied") or []
    last["undo"] = None
    last["undone"] = True
    return applied
