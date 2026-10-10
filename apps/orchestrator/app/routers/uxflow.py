"""
Stage 10 -- UX Flow & Design Specification (2026-10-10).

One flow document per BRD/PRD module (RELA-002 -> RELA-FL-002), drafted
from the baselined requirement, the module's Flow Design steps, its frozen
UI/UX screens and the Technical Design APIs. Same review loop as every
other stage (comment -> proposal, open questions answered or deferred,
approve -> freeze); the baseline is additionally guarded by the automatic
freeze gates in app/uxflow.py. Baselining opens Ready to Build.
"""
import json

from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response

from .. import ai_router, blueprint, export, reqdoc, review, store, uxflow
from ..models import FlowDoc, FlowStep, Journey, ScreenStates, SessionState, UXFlow

SCHEMA = """Respond with ONLY one JSON object:
{
  "journeys": [
    {"title": "<journey name>", "persona": "<who>", "trigger": "<what starts it>",
     "outcome": "<the success state the user ends in>",
     "entry_from": "<previous module or 'outside the product'>", "exits_to": "<next module, or ''>",
     "steps": [
       {"actor": "User|<system name>", "action": "<what they do>", "screen": "<EXACT screen name from the list>",
        "response": "<what the product does or shows>", "background": "<work that continues out of sight, or ''>",
        "api": "<METHOD /path from the API list if this step calls one, else ''>",
        "criteria": ["Given ..., when ..., then ..."]}
     ]}
  ],
  "screen_states": [
    {"screen": "<EXACT screen name>", "empty": "<what the user sees with no data, or 'n/a'>",
     "loading": "<while waiting / analysing, or 'n/a'>", "error": "<when something fails and how to recover>",
     "offline": "<with no connection, or 'n/a'>"}
  ],
  "microcopy": ["<Screen · element: exact text>"],
  "notes": ["<design decision worth recording>"],
  "open_questions": ["<only real UX decisions the product owner must still make>"]
}
Rules: 1-3 journeys covering ONLY this module's span (its own start and outcome; name the module it hands over to in
exits_to). 3-8 steps per journey, in order. Every step uses one of the listed screens, spelled exactly. Every listed
screen gets one screen_states entry with all four states (write 'n/a' only when the state truly cannot happen). Every
step has at least one testable criterion. Only use APIs from the list; never invent one. Plain business language."""


def code(state) -> str:
    from .techdesign import code as c
    return c(state)


async def plan(state: SessionState) -> list:
    have = {f.ui_id for f in state.ux_flows}
    c = code(state)
    return [UXFlow(fl_id=f"{c}-FL-{m.ui_id.split('-')[-1]}", module=m.module, req_id=m.req_id, ui_id=m.ui_id, title=m.title)
            for m in state.ui_modules if m.doc and m.ui_id not in have]


def parse(d: dict, fl_id: str) -> FlowDoc:
    def s(x):
        return reqdoc._clean(x) if x is not None else ""
    journeys = []
    raw = [x for x in (d.get("journeys") or []) if isinstance(x, dict)
           and isinstance(x.get("steps"), list) and any(isinstance(y, dict) for y in x["steps"])]
    for j_i, j in enumerate(raw[:4], 1):
        jid = f"J{j_i}"
        steps = []
        for k, st in enumerate([x for x in j["steps"] if isinstance(x, dict)][:12], 1):
            steps.append(FlowStep(step_id=f"{fl_id}.{jid}.{k}", actor=s(st.get("actor")) or "User", action=s(st.get("action")),
                                  screen=s(st.get("screen")), response=s(st.get("response")), background=s(st.get("background")),
                                  api=s(st.get("api")), criteria=[s(c) for c in (st.get("criteria") or []) if s(c)][:4]))
        journeys.append(Journey(journey_id=jid, title=s(j.get("title")), persona=s(j.get("persona")), trigger=s(j.get("trigger")),
                                outcome=s(j.get("outcome")), entry_from=s(j.get("entry_from")), exits_to=s(j.get("exits_to")), steps=steps))
    states = [ScreenStates(screen=s(x.get("screen")), **{k: s(x.get(k)) for k in uxflow.STATE_KEYS})
              for x in (d.get("screen_states") or []) if isinstance(x, dict) and s(x.get("screen"))]
    return FlowDoc(journeys=journeys, screen_states=states,
                   microcopy=[s(x) for x in (d.get("microcopy") or []) if s(x)][:30],
                   notes=[s(x) for x in (d.get("notes") or []) if s(x)],
                   open_questions=[s(x) for x in (d.get("open_questions") or []) if s(x)][:6])


def _screens_text(m) -> str:
    out = []
    for sc in m.doc.screens:
        acts = []
        for b in sc.blocks:
            for i, a in enumerate(b.actions or []):
                t = b.targets[i] if b.targets and i < len(b.targets) else ""
                acts.append(f"{a} -> {t}" if t and not t.startswith("#") else a)
        line = f"- {sc.name} [{sc.layout}{', uploaded design' if sc.source == 'upload' else ''}]: {sc.purpose}"
        if acts:
            line += " | buttons: " + "; ".join(acts[:8])
        if sc.states:
            line += " | states noted: " + "; ".join(sc.states)
        out.append(line)
    return "\n".join(out)


async def draft(state: SessionState, item: UXFlow, instruction: str | None) -> FlowDoc:
    m = next((u for u in state.ui_modules if u.ui_id == item.ui_id), None)
    if not m or not m.doc:
        raise RuntimeError("this module has no screens")
    r = await store.get_requirement(state.session_id, item.req_id)
    brd = reqdoc.render_text(r.title, r.doc) if r and r.doc else (r.body if r else "")
    mf = next((f for f in state.module_flows if f.module.lower() == item.module.lower()), None)
    td = next((t for t in state.tech_designs if t.req_id == item.req_id and t.doc), None)
    apis = "\n".join(f"- {a.method.upper()} {a.path}: {a.purpose}" for a in (td.doc.apis if td else []))
    order = [u.module for u in state.ui_modules]
    i = order.index(item.module) if item.module in order else -1
    bp = state.brand.blueprint if state.brand else None
    prompt = (
        f"Product: {state.selected_name} — {state.brand.tagline if state.brand and state.brand.tagline else ''}\n"
        f"Concept: {state.concept_summary}\n"
        + (f"Experience Blueprint (frozen): {blueprint.summary_text(bp)}\n" if bp else "")
        + f"Module: {item.module} ({item.req_id} -> {item.ui_id} -> {item.fl_id}). "
        f"Previous module: {order[i - 1] if i > 0 else 'none'}; next module: {order[i + 1] if 0 <= i < len(order) - 1 else 'none'}.\n\n"
        f"Baselined BRD/PRD requirement:\n{brd}\n\n"
        + (f"Agreed business flow (Flow Design stage):\n" + "\n".join(f"{n}. {x}" for n, x in enumerate(mf.steps, 1)) + "\n\n" if mf and mf.steps else "")
        + f"Frozen UI/UX screens of this module (use these names exactly):\n{_screens_text(m)}\n\n"
        + (f"Technical Design APIs of this module:\n{apis}\n\n" if apis else "No APIs are defined for this module.\n\n")
        + "Write the UX Flow & Design Specification for this module: the user journeys over these screens. " + SCHEMA
    )
    if instruction and item.doc:
        prompt += "\n\nCurrent flow document:\n" + json.dumps(item.doc.model_dump(), ensure_ascii=False) + f"\n\n{instruction}"
    result = await ai_router.generate(
        ai_router.Feature.TECH_DESIGN_GENERATION, prompt,
        system="You are a senior UX lead writing the frozen user-flow specification of a product, traceable to its requirements. JSON only.",
    )
    try:
        doc = parse(reqdoc._extract_json(result["text"]), item.fl_id)
    except (ValueError, json.JSONDecodeError):
        raise RuntimeError("the AI did not return a usable flow")
    if not doc.journeys:
        raise RuntimeError("the AI returned no journeys")
    return doc


def ready(state: SessionState) -> str | None:
    if not any(b.doc_type == "uiux" for b in state.baselines):
        return "baseline the UI/UX screens before writing the user flows"
    return None


async def _file(state):
    from .. import documents
    return await documents.archive(state, "uxflow")


KIND = review.Kind(
    doc_type="uxflow", label="UX Flow", list_attr="ux_flows", id_attr="fl_id", gen_attr="ux_generation",
    stage="uxflow", next_stage="complete", plan=plan, draft=draft,
    record_deferred=lambda doc, t: doc.notes.append(f"Deferred to a later release: {t}"), ready=ready,
    on_baseline=_file, gate=uxflow.gate_error,
)
router = review.make_router(KIND)


@router.get("/{session_id}/gates")
async def get_gates(session_id: str):
    return uxflow.gate_report(await review._session(session_id))


@router.get("/{session_id}/navmap")
async def get_navmap(session_id: str):
    return uxflow.navmap(await review._session(session_id))


def _version(state) -> str:
    v = [b.version for b in state.baselines if b.doc_type == "uxflow"]
    return v[-1] if v else "draft"


@router.get("/{session_id}/export/uxs.docx")
async def export_uxs(session_id: str):
    state = await review._session(session_id)
    if not any(f.doc for f in state.ux_flows):
        raise HTTPException(400, "no user flows to export yet")
    reqs = sorted(await store.list_requirements(state.session_id), key=lambda r: r.req_id)
    data, name = uxflow_docx(state, reqs)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{session_id}/export/tokens.json")
async def export_tokens(session_id: str):
    state = await review._session(session_id)
    name = export.file_name(state, "tokens", _version(state))
    return Response(uxflow.tokens_json(state), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{session_id}/navmap.html", response_class=HTMLResponse)
async def navmap_html(session_id: str):
    state = await review._session(session_id)
    return HTMLResponse(navmap_page(state))


# ------------------------------------------------------------------ document
def navmap_page(state) -> str:
    """Navigation map as a self-contained HTML page: every screen, grouped by
    module, with where each one leads (button, menu, link)."""
    from html import escape as E
    nm = uxflow.navmap(state)
    names = {n["key"]: n for n in nm["nodes"]}
    pal = __import__("app.ui_render", fromlist=["brand_palette"]).brand_palette(state)
    p = pal.primary if pal else "#FF7200"
    rows, last = [], None
    for n in nm["nodes"]:
        if n["module"] != last:
            rows.append(f'<h2>{E(n["ui_id"])} · {E(n["module"])}</h2>')
            last = n["module"]
        outs = [e for e in nm["edges"] if e["from"] == n["key"] and e["kind"] != "menu"]
        menu = any(e["from"] == n["key"] and e["kind"] == "menu" for e in nm["edges"])
        links = "".join(f'<li><b>{E(e["label"])}</b> → {E(names[e["to"]]["name"])} <small>{E(names[e["to"]]["module"])}</small></li>' for e in outs)
        dead = "".join(f'<li class="dead"><b>{E(d["label"])}</b> → “{E(d["target"])}” (not a screen)</li>' for d in nm["dead"] if d["from"] == n["key"])
        flag = " unreach" if any(u["key"] == n["key"] for u in nm["unreachable"]) else ""
        entry = ' <span class="tag">Entry</span>' if n["key"] == nm["entry"] else ""
        rows.append(f'<div class="node{flag}"><div class="nm">{E(n["name"])}{entry} <small>{E(n["ref"])} · {E(n["layout"])}</small></div>'
                    f'<ul>{links}{dead}{"<li class=menu>Menu / tabs → every module</li>" if menu else ""}</ul></div>')
    return ("<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{E(state.selected_name or '')} — navigation map</title><style>"
            f"body{{font:14px/1.5 system-ui,sans-serif;margin:0;padding:20px;background:#fafafa;color:#1a1a1a}}h1{{font-size:20px}}"
            f"h2{{font-size:15px;margin:22px 0 8px;color:{p}}}.node{{background:#fff;border:1px solid #e5e5e5;border-left:4px solid {p};border-radius:8px;padding:10px 14px;margin:8px 0}}"
            ".node.unreach{border-left-color:#d92d20;background:#fff6f5}.nm{font-weight:600}.nm small,li small{color:#777;font-weight:400}"
            "ul{margin:6px 0 0;padding-left:18px}li.dead{color:#b42318}li.menu{color:#777}.tag{background:#e8f5ee;color:#1d7a46;border-radius:999px;padding:1px 8px;font-size:11px}"
            f"</style></head><body><h1>{E(state.selected_name or '')} — navigation map</h1>"
            f"<p>{len(nm['nodes'])} screens · {len([e for e in nm['edges'] if e['kind'] != 'menu'])} links · "
            f"{len(nm['dead'])} dead buttons · {len(nm['unreachable'])} unreachable screens</p>{''.join(rows)}</body></html>")


def uxflow_docx(state, reqs) -> tuple[bytes, str]:
    """Phoneme UX Flow & Design Specification (corporate template). Module
    numbering mirrors the BRD/PRD (BRD 4.n -> UXS 3.n)."""
    from datetime import datetime, timezone
    version, status = export._version(state, "uxflow")
    fname = export.file_name(state, "uxflow", version)
    pcode = export.project_code(state)
    b = export.PhonemeDoc(state, "UX FLOW / DESIGN", state.selected_name or "Product", "UX Flow & Design Specification")
    b.cover()
    b.start_body()
    order = {r.req_id: i for i, r in enumerate(reqs, 1)}
    flows = sorted([f for f in state.ux_flows if f.doc], key=lambda f: order.get(f.req_id, 999))
    by_id = {f.fl_id: order.get(f.req_id) for f in flows}
    reviewed, approved = export._reviewers(state, "uxflow")
    b.document_control(
        f"UX Flow & Design Specification — {state.selected_name}",
        f"{pcode}-UXS, Version {version} — {status}",
        export.relative_path(state, "uxflow", version),
        export._change_rows(state, "uxflow", lambda ids: ", ".join(f"3.{by_id[i]}" if by_id.get(i) else "All" for i in ids) or "All"),
        export._date(datetime.now(timezone.utc).isoformat()), reviewed, approved,
    )
    v = lambda t: (lambda x: x[-1] if x else "draft")([x.version for x in export._baselines(state, t)])  # noqa: E731

    b.h("1. Introduction", 1)
    b.h("1.1 Purpose", 2)
    b.p(f"This document freezes how people use {state.selected_name}: every user journey from its trigger to its success "
        "outcome, the screen each step happens on, what every screen shows when it is empty, loading, failing or offline, "
        "the fixed wording, the navigation map and the design tokens. Together with the BRD/PRD and the Technical Design "
        "it completes the documentation baseline the build team works from.")
    b.h("1.2 References", 2)
    b.bullets([export.relative_path(state, "brdprd", v("brdprd")), export.relative_path(state, "techdesign", v("techdesign")),
               export.relative_path(state, "uiux", v("uiux")), export.relative_path(state, "prototype", v("uiux")),
               export.relative_path(state, "tokens", version)])
    b.h("1.3 Traceability", 2)
    b.p("Every step carries an ID of the form <module flow>.J<journey>.<step>. Each module traces BRD requirement → "
        "Technical Design → UI/UX screens → UX flow:")
    tds = {t.req_id: t.td_id for t in state.tech_designs if t.kind == "lld"}
    b.table(["BRD/PRD", "Technical Design", "UI/UX", "UX Flow", "Module"],
            [[f.req_id, tds.get(f.req_id, "—"), f.ui_id, f.fl_id, f.module] for f in flows] or [["—"] * 5],
            widths=[0.16, 0.2, 0.18, 0.18, 0.28])

    b.h("2. Experience Frame", 1)
    bp = state.brand.blueprint if state.brand else None
    b.h("2.1 Experience Blueprint", 2)
    b.p((f"Frozen at Identity, v{bp.version}. " if bp and bp.version else "Not frozen. ") + (blueprint.summary_text(bp) if bp else ""))
    b.h("2.2 Design tokens", 2)
    t = uxflow.tokens(state)
    rows = [[f"Colour · {k}", val] for k, val in t["color"].items()]
    rows += [["Heading font", t["font"]["heading"]], ["Body font", t["font"]["body"]],
             ["Corners", f"{t['radius']['name']} (cards {t['radius']['card']} px, buttons {t['radius']['button']} px)"],
             ["Density", f"{t['spacing']['name']} (gap {t['spacing']['gap']} px)"]]
    b.table(["Token", "Value"], rows, widths=[0.35, 0.65], label_col=True)
    b.h("2.3 Navigation map", 2)
    nm = uxflow.navmap(state)
    names = {n["key"]: n for n in nm["nodes"]}
    b.p(f"{len(nm['nodes'])} screens; entry point: {names[nm['entry']]['name'] if nm['entry'] in names else '—'}. "
        f"Every signed-in screen also reaches every module through the {'tab bar' if bp and bp.platforms != 'web' else 'menu'}.")
    b.table(["Screen", "Leads to"], [
        [f"{n['name']} ({n['ref']})", "; ".join(f"{e['label']} → {names[e['to']]['name']}" for e in nm["edges"] if e["from"] == n["key"] and e["kind"] != "menu") or "—"]
        for n in nm["nodes"]], widths=[0.4, 0.6], font_size=8.5)

    b.h("3. User Journeys by Module", 1)
    for f in flows:
        n = order.get(f.req_id, "")
        b.h(f"3.{n} {f.module} ({f.req_id} → {f.fl_id})", 2)
        for j in f.doc.journeys:
            b.h(f"3.{n}.{j.journey_id[1:]} {j.title}", 3, toc=False)
            b.table(["Persona", "Trigger", "Success outcome", "From → to"],
                    [[j.persona or "—", j.trigger or "—", j.outcome or "—", f"{j.entry_from or '—'} → {j.exits_to or '—'}"]],
                    widths=[0.18, 0.28, 0.32, 0.22], font_size=8.5)
            b.table(["Step", "Who · action", "Screen", "Product response", "Acceptance criteria"],
                    [[s.step_id.split(".", 1)[-1], f"{s.actor}: {s.action}", s.screen,
                      s.response + (f" (background: {s.background})" if s.background else "") + (f" [{s.api}]" if s.api else ""),
                      " ".join(s.criteria)] for s in j.steps] or [["—"] * 5],
                    widths=[0.08, 0.22, 0.17, 0.25, 0.28], font_size=8)
        if f.doc.screen_states:
            b.p("Screen states", bold=True, justify=False)
            b.table(["Screen", "Empty", "Loading", "Error", "Offline"],
                    [[x.screen, x.empty, x.loading, x.error, x.offline] for x in f.doc.screen_states],
                    widths=[0.18, 0.2, 0.2, 0.22, 0.2], font_size=8)
        if f.doc.microcopy:
            b.p("Fixed wording", bold=True, justify=False)
            b.bullets(f.doc.microcopy)
        if f.doc.notes:
            b.p("Design decisions", bold=True, justify=False)
            b.bullets(f.doc.notes)
        if f.decisions:
            b.table(["Question", "Decision"], [[x.question, ("Deferred — " + x.answer if x.answer else "Deferred") if x.deferred else x.answer]
                                               for x in f.decisions], widths=[0.5, 0.5])

    b.h("4. Freeze Gates", 1)
    rep = uxflow.gate_report(state)
    b.p("Checked automatically before the baseline. " + ("All required gates passed." if rep["passed"] else f"{rep['failed']} required gate(s) not yet passed."))
    b.table(["Gate", "Level", "Result", "Detail"],
            [[g["label"], "Required" if g["level"] == "must" else "Advisory", "Passed" if g["ok"] else "Open",
              "; ".join(g["detail"][:6]) + (" …" if len(g["detail"]) > 6 else "") or "—"] for g in rep["gates"]],
            widths=[0.3, 0.12, 0.1, 0.48], font_size=8.5)

    b.h("5. Road Ahead", 1)
    b.numbered(["Build each module in BRD/PRD order against these journeys and screens",
                "Test every step's acceptance criteria; the health agent monitors the same journeys in production",
                "Any change after this baseline goes through unfreeze → re-baseline (v1.1 …) with a Change Log row"])
    return b.bytes(), fname
