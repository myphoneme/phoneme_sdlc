"""
UX Flow & Design Specification (2026-10-10) -- the last document of the
Phoneme SDLC documentation stage.

The UI/UX stage draws the screens; this stage freezes how people move
through them: journeys (trigger -> steps -> success outcome), the state of
every screen (empty / loading / error / offline), fixed microcopy, the
navigation map and design tokens, each step traceable

    BRD RELA-002 -> step RELA-FL-002.J1.3 -> screen RELA-UI-002/S1 -> API RELA-TD-002

Freezing is guarded by automatic gates (gates()); when they all pass and
every module's flow is frozen, the UXS is baselined and Ready to Build
opens with the full Documentation Baseline.
"""
import json
import re
from dataclasses import asdict, dataclass, field

from . import ui_render

STATE_KEYS = ("empty", "loading", "error", "offline")


# ------------------------------------------------------------------ navigation map
def _modules(state):
    return [m for m in state.ui_modules if m.doc]


def navmap(state) -> dict:
    """Every screen and every way to move between them, exactly as the
    clickable prototype wires them (ui_render.Flow)."""
    mods = _modules(state)
    flow = ui_render.Flow(state, mods)
    nodes, edges, dead = [], [], []
    nav_first = [flow.first_of[m.module] for m in mods if m.module in flow.first_of]

    seen_e = set()

    def add(a, b, label, kind):
        if a and b and a != b and (a, b, label) not in seen_e:
            seen_e.add((a, b, label))
            edges.append({"from": a, "to": b, "label": label, "kind": kind})

    for m, s, key in flow.items:
        nodes.append({"key": key, "ref": f"{m.ui_id}/{s.screen_id}", "name": s.name, "module": m.module,
                      "ui_id": m.ui_id, "layout": s.layout, "source": s.source})
        has_button = False
        for b in s.blocks:
            for i, label in enumerate(b.actions or []):
                tgt = (b.targets[i] if b.targets and i < len(b.targets) else "").strip()
                if tgt.startswith("#"):
                    continue
                has_button = True
                if tgt:
                    dest = flow.by_name(m, tgt)
                    if dest:
                        add(key, dest, label, "button")
                    else:
                        dead.append({"from": key, "screen": s.name, "module": m.module, "label": label, "target": tgt})
                elif i == 0:
                    add(key, flow.next_of(key), label, "next")
        if s.source == "upload" or (not has_button and s.layout not in ("public", "auth")):
            add(key, flow.next_of(key), "Continue", "next")  # prototype: the design itself clicks through
        if s.layout in ("app", "mobile"):
            for k in nav_first:
                add(key, k, "Menu", "menu")
        if s.layout in ("public", "auth"):
            for k, label in ((flow.signin, "Sign in"), (flow.signup, "Get started"), (flow.landing, "Home")):
                add(key, k, label, "link")
    entry = flow.landing or (flow.items[0][2] if flow.items else None)
    seen, todo = set(), [entry] if entry else []
    out = {}
    for e in edges:
        out.setdefault(e["from"], []).append(e["to"])
    while todo:
        k = todo.pop()
        if k in seen:
            continue
        seen.add(k)
        todo.extend(out.get(k, []))
    unreachable = [n for n in nodes if n["key"] not in seen]
    return {"entry": entry, "nodes": nodes, "edges": edges, "dead": dead, "unreachable": unreachable}


# ------------------------------------------------------------------ helpers
def _norm(x: str) -> str:
    return " ".join((x or "").lower().split())


def screens_index(state) -> dict:
    """lower-case screen name -> list of (module, screen)."""
    idx = {}
    for m in _modules(state):
        for s in m.doc.screens:
            idx.setdefault(_norm(s.name), []).append((m, s))
    return idx


def resolve(state, module: str, name: str):
    hits = screens_index(state).get(_norm(name)) or []
    for m, s in hits:
        if m.module == module:
            return m, s
    return hits[0] if hits else (None, None)


def _api_key(a: str) -> str:
    m = re.match(r"\s*([A-Za-z]+)\s+(\S+)", a or "")
    if not m:
        return ""
    path = re.sub(r"\{[^}]*\}|:[A-Za-z_]+", "{}", m.group(2).rstrip("/"))
    return f"{m.group(1).upper()} {path.lower()}"


def known_apis(state) -> set:
    return {_api_key(f"{a.method} {a.path}") for t in state.tech_designs if t.doc for a in t.doc.apis}


def states_for(state) -> dict:
    """lower-case screen name -> merged ScreenStates fields from every flow doc."""
    out = {}
    for f in state.ux_flows:
        for st in (f.doc.screen_states if f.doc else []):
            cur = out.setdefault(_norm(st.screen), {k: "" for k in STATE_KEYS})
            for k in STATE_KEYS:
                cur[k] = cur[k] or (getattr(st, k) or "").strip()
    return out


# ------------------------------------------------------------------ gates
@dataclass
class Gate:
    key: str
    label: str
    level: str = "must"  # must (blocks the baseline) | should (shown, does not block)
    ok: bool = True
    detail: list = field(default_factory=list)


def gates(state) -> list[Gate]:
    mods = _modules(state)
    flows = {f.ui_id or f.req_id: f for f in state.ux_flows}
    out: list[Gate] = []

    g = Gate("screens_frozen", "UI/UX screens are baselined and unchanged")
    ui_b = [b for b in state.baselines if b.doc_type == "uiux"]
    if not ui_b:
        g.ok, g.detail = False, ["Baseline the UI/UX stage first."]
    else:
        from . import review
        from .routers.uiux import KIND as UI_KIND
        st = review.baseline_status(UI_KIND, state)
        if st["changed_since"] or not st["all_frozen"]:
            g.ok, g.detail = False, ["Screens changed since UI/UX v" + ui_b[-1].version + ": " + ", ".join(st["changed_since"] or ["unfrozen modules"]) + " — re-baseline UI/UX."]
    out.append(g)

    g = Gate("trace", "Every BRD/PRD requirement has its journeys")
    for m in mods:
        f = flows.get(m.ui_id)
        if not f or not f.doc or not any(j.steps for j in f.doc.journeys):
            g.ok = False
            g.detail.append(f"{m.req_id} {m.module}: no journey yet")
    out.append(g)

    g = Gate("screens_exist", "Every step happens on a real screen")
    for f in state.ux_flows:
        for j in (f.doc.journeys if f.doc else []):
            for s in j.steps:
                if s.screen and resolve(state, f.module, s.screen)[1] is None:
                    g.ok = False
                    g.detail.append(f"{s.step_id}: screen “{s.screen}” does not exist")
                elif not s.screen:
                    g.ok = False
                    g.detail.append(f"{s.step_id}: no screen named")
    out.append(g)

    g = Gate("testable", "Every step has acceptance criteria (Given / When / Then)")
    for f in state.ux_flows:
        for j in (f.doc.journeys if f.doc else []):
            for s in j.steps:
                if not [c for c in s.criteria if c.strip()]:
                    g.ok = False
                    g.detail.append(f"{s.step_id}: {s.action or 'step'} — no acceptance criterion")
    out.append(g)

    g = Gate("outcomes", "Every journey ends in a success state")
    for f in state.ux_flows:
        for j in (f.doc.journeys if f.doc else []):
            if not j.outcome.strip():
                g.ok = False
                g.detail.append(f"{f.fl_id}.{j.journey_id} {j.title}: no success outcome")
    out.append(g)

    nm = navmap(state)
    g = Gate("navigation", "No dead buttons and no unreachable screens")
    for d in nm["dead"]:
        g.ok = False
        g.detail.append(f"{d['module']} · {d['screen']}: “{d['label']}” leads to “{d['target']}”, which is not a screen")
    for n in nm["unreachable"]:
        g.ok = False
        g.detail.append(f"{n['module']} · {n['name']}: nothing leads here")
    out.append(g)

    g = Gate("states", "Every screen has its states (empty, loading, error, offline)")
    st = states_for(state)
    for m in mods:
        for s in m.doc.screens:
            have = st.get(_norm(s.name), {})
            miss = [k for k in STATE_KEYS if not have.get(k)]
            if miss:
                g.ok = False
                g.detail.append(f"{m.module} · {s.name}: " + ", ".join(miss) + " not described")
    out.append(g)

    g = Gate("tokens", "Screens follow the frozen brand and Experience Blueprint")
    bp = state.brand.blueprint if state.brand else None
    if not ui_render.brand_palette(state):
        g.ok = False
        g.detail.append("No brand palette — choose colours at Identity.")
    if not bp or not bp.version:
        g.ok = False
        g.detail.append("Experience Blueprint is not frozen — freeze it at Identity (look back to step 3).")
    ups = [f"{m.module} · {s.name}" for m in mods for s in m.doc.screens if s.source == "upload"]
    if ups:
        g.detail.append("Uploaded designs are checked by the owner, not automatically: " + "; ".join(ups))
    out.append(g)

    g = Gate("apis", "Every API a step calls exists in the Technical Design")
    apis = known_apis(state)
    for f in state.ux_flows:
        for j in (f.doc.journeys if f.doc else []):
            for s in j.steps:
                if s.api.strip() and _api_key(s.api) not in apis:
                    g.ok = False
                    g.detail.append(f"{s.step_id}: {s.api} is not in the Technical Design — add it there (re-baseline) or change the step")
    out.append(g)

    g = Gate("questions", "No open design questions")
    for f in state.ux_flows:
        for q in (f.doc.open_questions if f.doc else []):
            g.ok = False
            g.detail.append(f"{f.fl_id}: {q}")
    for m in state.ui_modules:
        for q in (m.doc.open_questions if m.doc else []):
            g.ok = False
            g.detail.append(f"{m.ui_id}: {q}")
    out.append(g)

    g = Gate("coverage", "Every screen is used by at least one journey", level="should")
    used = {_norm(s.screen) for f in state.ux_flows for j in (f.doc.journeys if f.doc else []) for s in j.steps}
    for m in mods:
        for s in m.doc.screens:
            if _norm(s.name) not in used:
                g.ok = False
                g.detail.append(f"{m.module} · {s.name}")
    out.append(g)
    return out


def gate_report(state) -> dict:
    gs = gates(state)
    must = [x for x in gs if x.level == "must"]
    return {"passed": all(x.ok for x in must), "failed": sum(1 for x in must if not x.ok),
            "gates": [asdict(x) for x in gs]}


def gate_error(state):
    r = gate_report(state)
    if r["passed"]:
        return None
    first = next(g for g in r["gates"] if g["level"] == "must" and not g["ok"])
    return f"{r['failed']} freeze gate{'s' if r['failed'] != 1 else ''} not passed — first: {first['label']}" + (f" ({first['detail'][0]})" if first["detail"] else "")


# ------------------------------------------------------------------ design tokens
def tokens(state) -> dict:
    pal = ui_render.brand_palette(state)
    bp = state.brand.blueprint if state.brand else None
    t = bp.tokens if bp else None
    radius = {"sharp": {"card": 6, "button": 4}, "rounded": {"card": 12, "button": 8}, "soft": {"card": 18, "button": 999}}
    space = {"compact": {"gap": 9, "card_padding": 10}, "comfortable": {"gap": 16, "card_padding": 16}}
    return {
        "product": state.selected_name,
        "blueprint_version": bp.version if bp else "",
        "color": {"primary": pal.primary, "ink": pal.ink, "surface": pal.surface, "accent": pal.accent,
                  "palette_name": pal.name} if pal else {},
        "font": {"heading": t.heading_font if t else "Space Grotesk", "body": t.body_font if t else "IBM Plex Sans"},
        "radius": radius.get(t.radius if t else "rounded", radius["rounded"]) | {"name": t.radius if t else "rounded"},
        "spacing": space.get(t.density if t else "comfortable", space["comfortable"]) | {"name": t.density if t else "comfortable"},
        "platforms": {"platforms": bp.platforms, "primary": bp.primary} if bp else {},
        "navigation": {"web": bp.web.nav, "home": bp.web.home, "phone_tabs": list(getattr(bp.mobile, "tabs", []) or [])} if bp else {},
    }


def tokens_json(state) -> bytes:
    return json.dumps(tokens(state), indent=2, ensure_ascii=False).encode()
