"""
Server-side renderer for UI/UX screen specs (2026-10-04).

Follows Phoneme's UI/UX mockup system: one page, brand palette as CSS
custom properties, a step nav numbered to match the BRD/PRD modules, and
one .section per screen with a browser-chrome .frame. The same HTML is
shown in the portal (iframe) and downloaded as the mockup deliverable, so
what is reviewed is exactly what is exported.
"""
import html
import re
from urllib.parse import quote

E = lambda s: html.escape(str(s or ""))  # noqa: E731

CSS = """
:root{--p:%(primary)s;--ink:%(ink)s;--surf:%(surface)s;--acc:%(accent)s;--bg:#f7f7f5;--line:#e6e3de;--mut:#62666d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "DM Sans",system-ui,sans-serif;overflow-x:hidden}
h1,h2,h3,h4{font-family:Manrope,system-ui,sans-serif;letter-spacing:-.02em;margin:0}
.intro{padding:32px 40px 8px}.brand{display:flex;align-items:center;gap:12px}.brand-mark{width:40px;height:40px;border-radius:10px;background:var(--p);color:#fff;display:grid;place-items:center;font:800 18px Manrope}
.brand h1{font-size:26px;color:var(--p)}.tagline{color:var(--mut);font-style:italic}
.stepnav{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 0;padding:0;list-style:none}.stepnav a{display:inline-flex;gap:8px;align-items:center;padding:6px 12px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--ink);text-decoration:none;font-weight:700;font-size:12.5px}.stepnav span{font:800 11px ui-monospace,monospace;color:var(--p)}
.section{padding:22px 40px}.step-tag{font:800 11px ui-monospace,monospace;letter-spacing:.08em;color:var(--p)}.section h2{font-size:20px;margin:4px 0}.section-sub{color:var(--mut);margin:0 0 14px}
.frame-scroll{overflow-x:auto}.frame{min-width:0;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 10px 30px #0000000d;overflow:hidden}
.frame.mobile{min-width:0;width:390px;margin:0 auto;border-radius:28px;border:8px solid #1b1b1b}
.chrome{display:flex;align-items:center;gap:6px;padding:10px 14px;background:#f1f0ee;border-bottom:1px solid var(--line)}.chrome i{width:10px;height:10px;border-radius:50%%;background:#d9d6d1}.url{margin-left:12px;flex:1;max-width:520px;padding:4px 12px;border-radius:999px;background:#fff;color:var(--mut);font-size:12px}
.appshell{display:flex;min-height:520px}.sidebar{width:210px;background:var(--ink);color:#fff;padding:16px 12px;flex-shrink:0}.sidebar .sb-brand{font:800 16px Manrope;margin:0 6px 16px;color:#fff}.navitem{padding:8px 10px;border-radius:8px;font-size:13px;opacity:.78}.navitem.on{background:var(--p);opacity:1;font-weight:700}
.main{flex:1;min-width:0;display:flex;flex-direction:column}.topbar{display:flex;align-items:center;justify-content:space-between;padding:12px 22px;border-bottom:1px solid var(--line)}.topbar h3{font-size:17px}.avatar{width:30px;height:30px;border-radius:50%%;background:var(--acc)}
.content{padding:20px 22px;display:flex;flex-direction:column;gap:14px}
.pubnav{display:flex;align-items:center;justify-content:space-between;padding:14px 26px;border-bottom:1px solid var(--line)}.pubnav b{color:var(--p);font:800 18px Manrope}.pubnav span{margin-left:18px;color:var(--mut);font-size:13px}.pubnav span.btn-primary{color:#fff}
.card{border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:#fff}.card h4{font-size:14.5px;margin-bottom:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}.tile{border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:var(--surf)}.tile b{display:block;font-size:13.5px}.tile small{color:var(--mut)}
.field{display:flex;flex-direction:column;gap:4px;margin-bottom:10px}.field label{font-size:12px;font-weight:700;color:var(--mut)}.field .in{height:36px;border:1px solid var(--line);border-radius:8px;background:#fbfbfa}
.btns{display:flex;gap:8px;flex-wrap:wrap}.btn{display:inline-flex;align-items:center;height:34px;padding:0 14px;border-radius:8px;border:1px solid var(--line);background:#fff;font-weight:700;font-size:13px}.btn-primary{background:var(--p);border-color:var(--p);color:#fff}
.tabs{display:flex;gap:6px}.tab{padding:6px 12px;border-radius:999px;background:#f1f0ee;font-size:12.5px;font-weight:700}.tab.on{background:var(--ink);color:#fff}
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}.stat{border:1px solid var(--line);border-radius:12px;padding:12px}.stat small{color:var(--mut);display:block}.stat b{font:800 22px Manrope}
table{width:100%%;border-collapse:collapse;font-size:13px}th{text-align:left;background:#f6f5f2;padding:8px 10px;border-bottom:1px solid var(--line)}td{padding:8px 10px;border-bottom:1px solid var(--line)}
.notebox{border-left:4px solid var(--acc);background:var(--surf);padding:10px 14px;border-radius:8px}
.stepper{display:flex;gap:10px;flex-wrap:wrap}.stepdot{display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700}.stepdot i{width:22px;height:22px;border-radius:50%%;display:grid;place-items:center;background:#f1f0ee;font-style:normal;font-size:11px}.stepdot.on i{background:var(--p);color:#fff}
.media{height:150px;border-radius:12px;background:repeating-linear-gradient(45deg,var(--surf),var(--surf) 10px,#fff 10px,#fff 20px);display:grid;place-items:center;color:var(--mut);font-weight:700}
ul.rows{list-style:none;margin:0;padding:0}ul.rows li{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid var(--line)}ul.rows li:last-child{border-bottom:0}
.pill{font-size:11px;font-weight:800;padding:2px 8px;border-radius:999px;background:var(--surf);color:var(--p)}
.states{margin:10px 0 0;color:var(--mut);font-size:12.5px}
.grid2>.frame,.grid3>.frame{min-width:0}
.upload-shot{cursor:pointer;text-align:center;background:#fff}.upload-shot img{max-width:100%%;height:auto;display:block;margin:0 auto;border-radius:8px}
.upload-pdf{width:100%%;height:900px;border:0}.image-content{padding:0}
[data-goto]{cursor:pointer}
"""


class Flow:
    """Navigation model for a set of modules: global screen order, link
    resolution (buttons -> named screens, primary button -> next screen),
    and how uploaded design files are referenced (URL or data URI)."""

    def __init__(self, state, modules, revised=False, asset=None):
        self.state, self.asset = state, (asset or (lambda s: ""))
        self.items = []  # (module, screen, key)
        self.first_of = {}
        for m in modules:
            doc = m.revised_doc if revised and m.revised_doc else m.doc
            for s in (doc.screens if doc else []):
                key = f"{m.ui_id}--{s.screen_id or s.name}".replace(" ", "_")
                self.items.append((m, s, key))
                self.first_of.setdefault(m.module, key)
        self.index = {k: i for i, (_, _, k) in enumerate(self.items)}
        acct = next((k for name, k in self.first_of.items() if name.lower().startswith("sign-in")), None)

        def find(pattern, layouts=None):
            rx = re.compile(pattern, re.I)
            return next((k for _, sc, k in self.items if rx.search(sc.name) and (not layouts or sc.layout in layouts)), None)
        self.landing = find(r"\b(landing|welcome|home ?page)\b", ("public",)) or acct
        self.signup = find(r"\b(create (an )?account|sign[ -]?up|register|get started)\b") or acct
        self.signin = find(r"^(sign[ -]?in|log[ -]?in)\b") or acct

    def key(self, m, s):
        return f"{m.ui_id}--{s.screen_id or s.name}".replace(" ", "_")

    def next_of(self, key):
        i = self.index.get(key)
        return self.items[i + 1][2] if i is not None and i + 1 < len(self.items) else None

    def by_name(self, m, name):
        n = (name or "").strip().lower()
        if not n:
            return None
        for mm, s, k in self.items:  # same module first
            if mm is m and s.name.lower() == n:
                return k
        for mm, s, k in self.items:
            if s.name.lower() == n or mm.module.lower() == n:
                return k
        return None


def _goto(target):
    return f' data-goto="{E(target)}"' if target else ""


def _split(s: str):
    for sep in (" — ", " - ", ": "):
        if sep in s:
            a, b = s.split(sep, 1)
            return a.strip(), b.strip()
    return s, ""


def block_html(b, ctx=None) -> str:
    """ctx = (flow, module, screen_key) for link resolution."""
    t, title = b.type, E(b.title)
    head = f"<h4>{title}</h4>" if b.title else ""
    if t == "text":
        return f'<div class="card">{head}<p style="margin:0">{E(b.text)}</p></div>'
    if t == "list":
        rows = "".join(f"<li><span>{E(a)}</span>{f'<span class=pill>{E(c)}</span>' if c else ''}</li>" for a, c in map(_split, b.items))
        return f'<div class="card">{head}<ul class="rows">{rows}</ul></div>'
    if t == "cards":
        tiles = "".join(f'<div class="tile"><b>{E(a)}</b><small>{E(c)}</small></div>' for a, c in map(_split, b.items))
        return f'{f"<h4>{title}</h4>" if b.title else ""}<div class="grid">{tiles}</div>'
    if t == "form":
        fields = "".join(f'<div class="field"><label>{E(x)}</label><input class="in" placeholder="{E(x)}"></div>' for x in b.items)
        return f'<div class="card">{head}{fields}{_btns(b.actions, b.targets, ctx)}</div>'
    if t == "buttons":
        return _btns(b.actions or b.items, b.targets, ctx)
    if t == "image":
        return _image(b, ctx)
    if t == "table":
        th = "".join(f"<th>{E(c)}</th>" for c in b.columns)
        tr = "".join("<tr>" + "".join(f"<td>{E(c)}</td>" for c in row) + "</tr>" for row in b.rows)
        return f'<div class="card">{head}<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'
    if t == "tabs":
        return '<div class="tabs">' + "".join(f'<span class="tab{" on" if i == 0 else ""}">{E(x)}</span>' for i, x in enumerate(b.items)) + "</div>"
    if t == "stats":
        return f'{head}<div class="stats">' + "".join(f'<div class="stat"><small>{E(a)}</small><b>{E(c or "—")}</b></div>' for a, c in map(_split, b.items)) + "</div>"
    if t == "notice":
        return f'<div class="notebox"><b>{title}</b> {E(b.text)}</div>'
    if t == "steps":
        return '<div class="stepper">' + "".join(f'<span class="stepdot{" on" if i == 0 else ""}"><i>{i + 1}</i>{E(x)}</span>' for i, x in enumerate(b.items)) + "</div>"
    if t == "media":
        return f'<div class="media">{title or E(b.text) or "Media"}</div>'
    if t == "header":
        return f'<div class="card" style="background:var(--surf)"><h3>{title}</h3><p style="margin:4px 0 0;color:var(--mut)">{E(b.text)}</p>{_btns(b.actions, b.targets, ctx)}</div>'
    return f'<div class="card">{head}<p style="margin:0">{E(b.text or ", ".join(b.items))}</p></div>'


def _btns(actions, targets=None, ctx=None) -> str:
    """Buttons link to their named target screen; the primary (first)
    button without a target goes to the next screen in the flow."""
    if not actions:
        return ""
    out = []
    for i, a in enumerate(actions):
        dest = None
        if ctx:
            flow, m, key = ctx
            tgt = (targets[i] if targets and i < len(targets) else "")
            dest = flow.by_name(m, tgt) if tgt else (flow.next_of(key) if i == 0 else None)
        out.append(f'<span class="btn{" btn-primary" if i == 0 else ""}"{_goto(dest)}>{E(a)}</span>')
    return '<div class="btns" style="margin-top:10px">' + "".join(out) + "</div>"


def _image(b, ctx) -> str:
    """An uploaded design (image or PDF). Clicking it moves to the next screen."""
    flow, m, key = ctx if ctx else (None, None, None)
    src = flow.asset(b.text) if flow else ""
    nxt = flow.next_of(key) if flow else None
    if b.title == "application/pdf":
        return (f'<object class="upload-pdf" data="{E(src)}" type="application/pdf"><p>PDF design: '
                f'<a href="{E(src)}">open</a></p></object>' + (f'<div class="btns"><span class="btn btn-primary"{_goto(nxt)}>Next screen →</span></div>' if nxt else ""))
    return f'<div class="upload-shot"{_goto(nxt)}><img alt="Uploaded design" src="{E(src)}"></div>'


def screen_html(state, screen, nav: list[str], active: str, domain: str, flow=None, module=None) -> str:
    key = flow.key(module, screen) if flow else ""
    ctx = (flow, module, key) if flow else None
    body = "" if screen.layout in ("public", "auth") else "".join(block_html(b, ctx) for b in screen.blocks)
    url = f"{domain}{screen.route or '/'}"
    name = E(state.selected_name or "Product")
    if screen.layout == "image":
        inner = f'<div class="content image-content">{body}</div>'
    elif screen.layout in ("public", "auth"):
        frame = (f'<div class="frame"><div class="chrome"><i></i><i></i><i></i><span class="url">{E(url)}</span></div>'
                 f'{site_page(state, screen, screen.blocks, flow, ctx)}</div>')
        return f'<div class="frame-scroll">{frame}</div>'
    elif screen.layout == "mobile":
        inner = f'<div class="topbar"><h3>{E(screen.name)}</h3><span class="avatar"></span></div><div class="content">{body}</div>'
    else:
        items = "".join(f'<div class="navitem{" on" if n == active else ""}"{_goto(flow.first_of.get(n) if flow else None)}>{E(n)}</div>' for n in nav)
        inner = (f'<div class="appshell"><aside class="sidebar"><div class="sb-brand">{name}</div>{items}</aside>'
                 f'<div class="main"><div class="topbar"><h3>{E(screen.name)}</h3><span class="avatar"></span></div><div class="content">{body}</div></div></div>')
    frame = f'<div class="frame{" mobile" if screen.layout == "mobile" else ""}"><div class="chrome"><i></i><i></i><i></i><span class="url">{E(url)}</span></div>{inner}</div>'
    return frame if screen.layout == "mobile" else f'<div class="frame-scroll">{frame}</div>'


def page(state, modules, revised: bool = False, title_suffix: str = "UI/UX mockups", asset=None) -> str:
    pal = state.brand.palette if state.brand and state.brand.palette else None
    css = CSS % {
        "primary": (pal.primary if pal else "#FF7200"), "ink": (pal.ink if pal else "#171717"),
        "surface": (pal.surface if pal else "#FFF7F0"), "accent": (pal.accent if pal else "#0F766E"),
    } + SITE_CSS
    domain = (state.brand.chosen_domain if state.brand and state.brand.chosen_domain else "app.example.com")
    nav = [m.module for m in state.ui_modules]
    def num(m, fallback):
        try:
            return int((m.req_id or "").split("-")[-1])
        except ValueError:
            return fallback
    stepnav = "".join(f'<li><a href="#{E(m.ui_id)}"><span>{num(m, i):02d}</span>{E(m.module)}</a></li>' for i, m in enumerate(modules, 1))
    flow = Flow(state, modules, revised, asset)
    sections = []
    for k, m in enumerate(modules, 1):
        i = num(m, k)
        doc = m.revised_doc if revised and m.revised_doc else m.doc
        if not doc:
            continue
        for j, s in enumerate(doc.screens, 1):
            sid = m.ui_id if j == 1 else f"{m.ui_id}-{j}"
            states = f'<p class="states"><b>States:</b> {E(" · ".join(s.states))}</p>' if s.states else ""
            sections.append(
                f'<section class="section" id="{E(sid)}"><span class="step-tag">STEP {i}.{j} · {E(m.module)}</span>'
                f'<h2>{E(s.name)}</h2><p class="section-sub">{E(s.purpose)}</p>'
                f'{screen_html(state, s, nav, m.module, domain, flow, m)}{states}</section>'
            )
    tagline = E(state.brand.tagline) if state.brand and state.brand.tagline else ""
    logo = state.brand.logo.svg if state.brand and state.brand.logo else ""
    mark = f'<img alt="" style="height:44px" src="data:image/svg+xml;charset=utf-8,{E(quote(logo))}">' if logo else f'<span class="brand-mark">{E((state.selected_name or "P")[:1])}</span>'
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{E(state.selected_name)} — {E(title_suffix)}</title>"
        "<link rel=preconnect href=https://fonts.googleapis.com><link href='https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Manrope:wght@700;800&family=Space+Grotesk:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap' rel=stylesheet>"
        f"<style>{css}</style></head><body>"
        f'<div class="intro"><div class="brand">{mark}<div><h1>{E(state.selected_name)}</h1><div class="tagline">{tagline}</div></div></div>'
        f'<ul class="stepnav">{stepnav}</ul></div>{"".join(sections)}</body></html>'
    )


PROTO_CSS = """
body{padding-top:64px}.proto-bar{position:fixed;inset:0 0 auto 0;z-index:10;display:flex;align-items:center;gap:10px;flex-wrap:wrap;
padding:10px 18px;background:var(--ink);color:#fff;font:600 13px "DM Sans",sans-serif;box-shadow:0 4px 16px #0003}
.proto-bar b{font:800 15px Manrope,sans-serif;margin-right:6px}.proto-bar select{max-width:360px;height:32px;border-radius:8px;border:0;padding:0 8px;font:600 13px "DM Sans",system-ui,sans-serif}
.proto-bar button{height:32px;padding:0 12px;border-radius:8px;border:1px solid #ffffff40;background:transparent;color:#fff;font:700 13px "DM Sans",system-ui,sans-serif;cursor:pointer}
.proto-bar button.primary{background:var(--p);border-color:var(--p)}.proto-bar .pos{opacity:.8}.proto-bar label{display:flex;gap:6px;align-items:center;margin-left:auto;cursor:pointer}
.proto-screen{display:none;padding:18px 24px 40px}.proto-screen.on{display:block}.proto-screen .section-sub{margin-bottom:10px}
body.hl [data-goto]{outline:2px dashed var(--p);outline-offset:3px;border-radius:8px}
.proto-hint{color:var(--mut);font-size:12.5px;margin:8px 0 0}
"""

PROTO_JS = """
(function(){var S=[].slice.call(document.querySelectorAll('.proto-screen'));if(!S.length)return;var i=0,
sel=document.getElementById('pSel'),pos=document.getElementById('pPos');
function show(k){var n=typeof k==='number'?k:S.findIndex(function(s){return s.id===k});if(n<0||n>=S.length)return;
S[i].classList.remove('on');i=n;S[i].classList.add('on');sel.value=S[i].id;pos.textContent='Screen '+(i+1)+' of '+S.length;
history.replaceState(null,'','#'+S[i].id);window.scrollTo(0,0);}
document.addEventListener('click',function(e){var t=e.target.closest('[data-goto]');if(t){e.preventDefault();show(t.getAttribute('data-goto'));return;}
var tab=e.target.closest('.tab');if(tab){[].forEach.call(tab.parentNode.querySelectorAll('.tab'),function(x){x.classList.remove('on')});tab.classList.add('on');}});
document.getElementById('pPrev').onclick=function(){show(i-1)};document.getElementById('pNext').onclick=function(){show(i+1)};
sel.onchange=function(){show(sel.value)};document.getElementById('pHl').onchange=function(e){document.body.classList.toggle('hl',e.target.checked)};
document.addEventListener('keydown',function(e){if(/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;if(e.key==='ArrowRight')show(i+1);if(e.key==='ArrowLeft')show(i-1);});
show(location.hash?location.hash.slice(1):0);if(S[i]&&!S[i].classList.contains('on'))show(0);})();
"""


def prototype(state, modules, asset=None) -> str:
    """Clickable prototype: one screen at a time, real navigation between
    screens (buttons, sidebar, Sign in, uploaded designs), a flow player
    to step through the whole journey, and a toggle that outlines every
    clickable element."""
    pal = state.brand.palette if state.brand and state.brand.palette else None
    css = CSS % {
        "primary": (pal.primary if pal else "#FF7200"), "ink": (pal.ink if pal else "#171717"),
        "surface": (pal.surface if pal else "#FFF7F0"), "accent": (pal.accent if pal else "#0F766E"),
    } + SITE_CSS
    domain = (state.brand.chosen_domain if state.brand and state.brand.chosen_domain else "app.example.com")
    flow = Flow(state, modules, False, asset)
    nav = [m.module for m in state.ui_modules]
    opts, screens, last_mod = [], [], None
    for n, (m, s, key) in enumerate(flow.items, 1):
        if m is not last_mod:
            if last_mod is not None:
                opts.append("</optgroup>")
            opts.append(f'<optgroup label="{E(m.ui_id)} · {E(m.module)}">')
            last_mod = m
        opts.append(f'<option value="{E(key)}">{n}. {E(s.name)}</option>')
        src = " · uploaded design" if s.source == "upload" else ""
        screens.append(
            f'<div class="proto-screen" id="{E(key)}"><span class="step-tag">{E(m.ui_id)} · {E(m.module)}{src}</span>'
            f'<h2>{E(s.name)}</h2><p class="section-sub">{E(s.purpose)}</p>'
            f'{screen_html(state, s, nav, m.module, domain, flow, m)}'
            f'<p class="proto-hint">Click buttons, the sidebar or the design itself to move through the flow — or use ← → / Previous · Next.</p></div>'
        )
    if opts:
        opts.append("</optgroup>")
    body = "".join(screens) or '<div class="section"><h2>No screens yet</h2></div>'
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{E(state.selected_name)} — clickable prototype</title>"
        "<link href='https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Manrope:wght@700;800&family=Space+Grotesk:wght@500;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap' rel=stylesheet>"
        f"<style>{css}{PROTO_CSS}</style></head><body>"
        f'<div class="proto-bar"><b>{E(state.selected_name)}</b><button id="pPrev">← Previous</button>'
        f'<select id="pSel" aria-label="Jump to screen">{"".join(opts)}</select><button id="pNext" class="primary">Next →</button>'
        f'<span class="pos" id="pPos"></span><label><input type="checkbox" id="pHl"> Highlight clickable areas</label></div>'
        f"{body}<script>{PROTO_JS}</script></body></html>"
    )


# ---------------------------------------------------------------------------
# Public site & auth pages (2026-10-06). A modern SaaS front door in the
# product's own brand: tinted neutrals mixed from the brand primary,
# Space Grotesk display headings over IBM Plex Sans text, a sticky
# translucent nav, pill CTAs, and a centred auth card for sign-in / sign-up.
# Sizes follow the frame width (container queries), so the same page reads
# well in the portal preview, the exported mockup and the prototype.
# ---------------------------------------------------------------------------
SITE_CSS = """
.site{--sbg:color-mix(in oklab,var(--p) 2.5%,#fff);--smut:color-mix(in oklab,var(--p) 4%,#f3f3f3);--sline:color-mix(in oklab,var(--p) 9%,#e4e4e4);
--sink:color-mix(in oklab,var(--p) 10%,#141414);--ssub:color-mix(in oklab,var(--p) 10%,#4f4f55);--gut:clamp(18px,7cqi,72px);
container-type:inline-size;background:var(--sbg);color:var(--sink);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif}
.site h1,.site h2,.site h3{font-family:"Space Grotesk",system-ui,sans-serif;font-weight:700;color:var(--sink)}
.snav{position:sticky;top:0;z-index:3;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px var(--gut);
background:color-mix(in oklab,var(--sbg) 72%,transparent);backdrop-filter:blur(10px);border-bottom:3px solid var(--p)}
.snav .wm{font:700 19px "Space Grotesk",system-ui,sans-serif;letter-spacing:-.02em;color:var(--sink)}.snav .wm{display:inline-flex;align-items:center;gap:8px;cursor:pointer}.snav .wm img{height:30px;max-width:90px}
.snav .links{display:flex;align-items:center;gap:clamp(10px,2.4cqi,26px);font-size:14px;font-weight:500}
.sbtn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:36px;padding:0 14px;border-radius:5px;font:500 14px "IBM Plex Sans",system-ui,sans-serif;color:var(--sink);white-space:nowrap}
.sbtn.solid{background:var(--p);color:#fff}.sbtn.pill{height:48px;padding:0 30px;border-radius:999px}.sbtn.outline{border:1px solid var(--sline);background:var(--sbg)}
.sbtn svg{width:16px;height:16px}
.hero{display:grid;grid-template-columns:1fr 1.05fr;gap:clamp(28px,5cqi,64px);align-items:center;padding:clamp(40px,8cqi,104px) var(--gut);border-bottom:1px solid var(--sline);
background:radial-gradient(60% 50% at 80% 10%,color-mix(in oklab,var(--p) 9%,transparent),transparent 70%)}
.eyepill{display:inline-flex;align-items:center;gap:8px;padding:5px 14px;border-radius:999px;background:var(--smut);border:1px solid var(--sline);color:var(--p);font:600 12px/1.3 "IBM Plex Sans",system-ui,sans-serif;letter-spacing:.18em;text-transform:uppercase}
.eyepill svg{width:14px;height:14px}
.hero h1{font-size:clamp(38px,6.6cqi,76px);line-height:1.02;letter-spacing:-.04em;margin:20px 0}
.lede{font-size:clamp(16px,1.7cqi,19px);color:var(--ssub);max-width:34em;margin:0}
.ctas{display:flex;flex-wrap:wrap;gap:12px;margin-top:30px}
.hero-media{position:relative;aspect-ratio:1/1.05;border-radius:28px;overflow:hidden;box-shadow:0 30px 80px color-mix(in oklab,var(--p) 22%,transparent);
background:radial-gradient(70% 60% at 30% 20%,color-mix(in oklab,var(--p) 55%,#1b1b2e),#111018 75%)}
.hero-media .glow{position:absolute;inset:auto -20% -30% -20%;height:70%;background:radial-gradient(50% 50% at 50% 50%,color-mix(in oklab,var(--p) 70%,#7c5cff),transparent 70%);opacity:.55}
.hm-card{position:absolute;left:9%;right:9%;top:12%;border-radius:18px;background:#ffffff14;border:1px solid #ffffff2e;backdrop-filter:blur(8px);padding:16px;color:#fff}
.hm-card .bar{display:flex;gap:6px;margin-bottom:12px}.hm-card .bar i{width:9px;height:9px;border-radius:50%;background:#ffffff40}
.hm-row{display:flex;align-items:center;gap:12px;padding:10px;border-radius:12px;background:#ffffff12;margin-top:8px;font-size:13px}
.hm-row .th{width:42px;height:32px;border-radius:8px;flex-shrink:0;background:linear-gradient(135deg,color-mix(in oklab,var(--p) 80%,#fff),#5b6cff)}
.hm-row:nth-child(3) .th{background:linear-gradient(135deg,#22c1a5,#3a7bd5)}.hm-row:nth-child(4) .th{background:linear-gradient(135deg,#f6a04d,#d2495f)}
.hm-row small{display:block;opacity:.65;font-size:11.5px}
.hm-chip{position:absolute;bottom:9%;right:7%;padding:10px 14px;border-radius:14px;background:#ffffffe8;color:var(--sink);font:600 13px "IBM Plex Sans",system-ui,sans-serif;box-shadow:0 10px 30px #0004}
.hm-chip b{color:var(--p)}
.promise{background:var(--smut);border-bottom:1px solid var(--sline);padding:30px var(--gut);text-align:center}
.cap{font:600 12px "IBM Plex Sans",system-ui,sans-serif;letter-spacing:.2em;text-transform:uppercase}
.promise ul{list-style:none;margin:16px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.promise li{display:flex;justify-content:center;align-items:center;gap:10px;padding:6px 16px;font-size:14.5px}.promise li+li{border-left:1px solid var(--sline)}
.promise svg,.plan li svg{width:16px;height:16px;color:var(--p);flex-shrink:0}
.feat{display:grid;grid-template-columns:1fr 1.2fr;gap:clamp(28px,6cqi,72px);padding:clamp(48px,9cqi,120px) var(--gut);align-items:start}
.eyebrow{color:var(--p);font:600 13px "IBM Plex Sans",system-ui,sans-serif;letter-spacing:.18em;text-transform:uppercase;margin:0 0 12px}
.site h2{font-size:clamp(30px,4.6cqi,50px);line-height:1.05;letter-spacing:-.035em;margin:0 0 16px}
.fsteps{display:flex;flex-direction:column;gap:18px;border-left:1px solid var(--sline);padding-left:0}
.fcard{display:grid;grid-template-columns:52px 1fr;gap:18px;padding:28px 32px;border:1px solid var(--sline);border-radius:12px;background:var(--smut);margin-left:-1px}
.fcard:nth-child(even){margin-left:clamp(0px,4cqi,42px);border-color:var(--p);border-radius:24px;background:var(--sbg)}
.ficon{width:50px;height:50px;border-radius:50%;background:var(--p);color:#fff;display:grid;place-items:center}.ficon svg{width:20px;height:20px}
.fnum{color:var(--p);font:700 12px "IBM Plex Sans",system-ui,sans-serif;letter-spacing:.2em}.fcard h3{font-size:clamp(19px,2.2cqi,24px);letter-spacing:-.02em;margin:4px 0 8px}.fcard p{margin:0;color:var(--ssub)}
.pricing{background:var(--smut);border-block:1px solid var(--sline);padding:clamp(48px,9cqi,120px) var(--gut)}
.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;margin-top:36px;align-items:start}
.plan{border:1px solid var(--sline);border-radius:12px;padding:32px 34px;background:var(--sbg)}
.plan.hl{border-color:var(--p);border-top:6px solid var(--p);border-radius:24px;background:var(--smut)}
.plan .ph{display:flex;justify-content:space-between;align-items:center;gap:10px}.plan .ph b{font-size:17px}
.badge{background:var(--p);color:#fff;border-radius:999px;padding:3px 12px;font:600 12.5px "IBM Plex Sans",system-ui,sans-serif}
.plan .desc{color:var(--ssub);margin:6px 0 18px;font-size:14.5px}.price{font:700 clamp(36px,4.4cqi,48px)/1 "Space Grotesk",system-ui,sans-serif;letter-spacing:-.03em}.price small{font:400 15px "IBM Plex Sans",system-ui,sans-serif;color:var(--ssub);letter-spacing:0;margin-left:4px}
.plan ul{list-style:none;padding:0;margin:22px 0 26px;display:grid;gap:10px;font-size:14.5px}.plan.hl ul{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}.plan li{display:flex;gap:10px;align-items:flex-start}
.plan .sbtn{width:100%}
.faq{max-width:760px;margin:0 auto;padding:clamp(48px,9cqi,104px) var(--gut);text-align:center}.faq h2{font-size:clamp(28px,3.6cqi,40px)}
.faq details{text-align:left;border-bottom:1px solid var(--sline)}.faq summary{list-style:none;display:flex;justify-content:space-between;align-items:center;padding:18px 0;font-weight:500;cursor:pointer}
.faq summary::-webkit-details-marker{display:none}.faq summary svg{width:16px;height:16px;transition:transform .2s}.faq details[open] summary svg{transform:rotate(180deg)}.faq details p{margin:0 0 18px;color:var(--ssub)}
.ctaband{margin:0 clamp(12px,4cqi,40px) clamp(48px,8cqi,96px);border-radius:28px;background:var(--p);color:#fff;padding:clamp(32px,5cqi,60px) clamp(24px,5cqi,56px);
display:grid;grid-template-columns:1fr auto;gap:24px;align-items:end}
.ctaband .eyebrow{color:#ffffffc0}.ctaband h2{color:#fff;margin:0 0 12px}.ctaband p{margin:0;color:#ffffffd0;font-size:17px}.ctaband .sbtn{background:#fff;color:var(--p);font-weight:600}
.sfoot{border-top:1px solid var(--sline);padding:44px var(--gut) 28px;display:grid;grid-template-columns:2fr 1fr 1fr;gap:24px;font-size:14.5px}
.sfoot b{display:block;margin-bottom:10px;font-weight:600}.sfoot .wm{font:700 19px "Space Grotesk",system-ui,sans-serif;margin-bottom:8px}.sfoot span{display:block;margin-bottom:8px}
.sfoot .copy{grid-column:1/-1;border-top:1px solid var(--sline);padding-top:20px;text-align:center;font-size:13px;color:var(--ssub)}
.spad{padding:28px var(--gut);display:flex;flex-direction:column;gap:14px}
.authwrap{display:grid;justify-items:center;padding:clamp(36px,7cqi,72px) 16px clamp(48px,8cqi,88px)}
.auth{width:100%;max-width:460px;background:var(--smut);border:1px solid var(--sline);border-radius:8px;box-shadow:0 2px 10px #0000000d;padding:28px 26px 24px;text-align:center}
.auth h2{font-size:26px;letter-spacing:-.02em;margin:0 0 6px}.auth .sub{margin:0 0 22px;font-size:14.5px}
.auth .af{text-align:left;margin-bottom:16px}.auth label{display:block;font-size:14px;font-weight:500;margin-bottom:6px}
.auth input{width:100%;height:40px;border:1px solid var(--sline);border-radius:6px;background:#fff;padding:0 12px;font:14px "IBM Plex Sans",system-ui,sans-serif;color:var(--sink)}
.auth .alink{display:block;text-align:right;margin:-8px 0 14px;font-size:13px;color:var(--p)}
.auth .sbtn.solid{width:100%;height:42px}.auth .switch{margin:16px 0 0;font-size:14px}.auth .switch span{color:var(--p);cursor:pointer}
@container (max-width:760px){.hero,.feat,.ctaband{grid-template-columns:1fr}.hero-media{aspect-ratio:4/3}.snav .links .hide-s{display:none}.sfoot{grid-template-columns:1fr 1fr}.sfoot>div:first-child{grid-column:1/-1}
.promise li+li{border-left:0}.fcard:nth-child(even){margin-left:0}}
"""

_ICON = {
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
    "send": '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "arrow": '<path d="M5 12h14M13 5l7 7-7 7"/>',
    "chev": '<path d="m6 9 6 6 6-6"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
}


def _svg(name: str) -> str:
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{_ICON[name]}</svg>')


def _dest(ctx, targets, i):
    if not ctx:
        return None
    flow, m, key = ctx
    tgt = targets[i] if targets and i < len(targets) else ""
    if tgt.startswith("#"):
        return None
    return flow.by_name(m, tgt) if tgt else (flow.next_of(key) if i == 0 else None)


def _sbtn(label, dest=None, cls="", icon=None, extra=""):
    ic = _svg(icon) if icon else ""
    return f'<span class="sbtn {cls}"{_goto(dest)}{extra}>{E(label)}{ic}</span>'


_SCROLL_FEAT = ' onclick="var f=this.closest(\'.site\').querySelector(\'.feat\');if(f)f.scrollIntoView({behavior:\'smooth\'})" style="cursor:pointer"'


def _site_actions(b, ctx, first_icon="arrow"):
    out = []
    for i, a in enumerate(b.actions[:2]):
        tgt = b.targets[i] if b.targets and i < len(b.targets) else ""
        extra = _SCROLL_FEAT if tgt.startswith("#") else ""
        out.append(_sbtn(a, _dest(ctx, b.targets, i), "pill solid" if i == 0 else "pill outline", first_icon if i == 0 else None, extra))
    return "".join(out)


def site_block(b, ctx=None):
    """Full-width section for the public-site block types; None if not one."""
    t = b.type
    if t == "hero":
        rows = [_split(x) for x in (b.items or [])][:3]
        rows = rows or [("Your workspace", "Everything in one place"), ("Today's highlights", "Ready when you are"), ("Shared with your team", "One click")]
        media_rows = "".join(f'<div class="hm-row"><span class="th"></span><div>{E(a)}<small>{E(c)}</small></div></div>' for a, c in rows)
        name = E(ctx[0].state.selected_name) if ctx else ""
        eyebrow = f'<span class="eyepill">{_svg("spark")}{E(b.eyebrow)}</span>' if b.eyebrow else ""
        return (f'<section class="hero"><div>{eyebrow}'
                f'<h1>{E(b.title)}</h1><p class="lede">{E(b.text)}</p><div class="ctas">{_site_actions(b, ctx)}</div></div>'
                f'<div class="hero-media" aria-hidden="true"><span class="glow"></span><div class="hm-card"><div class="bar"><i></i><i></i><i></i></div>'
                f'{media_rows}</div><div class="hm-chip"><b>{name}</b> · live preview</div></div></section>')
    if t == "promise":
        lis = "".join(f"<li>{_svg('check')}<span>{E(x)}</span></li>" for x in b.items[:4])
        return f'<section class="promise"><div class="cap">{E(b.eyebrow or b.title)}</div><ul>{lis}</ul></section>'
    if t == "features":
        icons = ["bolt", "chart", "layers", "send"]
        cards = "".join(
            f'<div class="fcard"><span class="ficon">{_svg(icons[i % 4])}</span><div><div class="fnum">{i + 1:02d}</div><h3>{E(a)}</h3><p>{E(c)}</p></div></div>'
            for i, (a, c) in enumerate(map(_split, b.items[:5])))
        return (f'<section class="feat"><div>{f"<p class=eyebrow>{E(b.eyebrow)}</p>" if b.eyebrow else ""}<h2>{E(b.title)}</h2>'
                f'<p class="lede">{E(b.text)}</p></div><div class="fsteps">{cards}</div></section>')
    if t == "pricing":
        plans = []
        for row in b.rows[:3]:
            name, price, period, desc, feats, badge = (list(row) + [""] * 6)[:6]
            hl = bool(badge)
            lis = "".join(f"<li>{_svg('check')}<span>{E(f.strip())}</span></li>" for f in feats.split(";") if f.strip())
            dest = ctx[0].signup if ctx else None
            plans.append(
                f'<div class="plan{" hl" if hl else ""}"><div class="ph"><b>{E(name)}</b>{f"<span class=badge>{E(badge)}</span>" if badge else ""}</div>'
                f'<p class="desc">{E(desc)}</p><div class="price">{E(price)}{f"<small>{E(period)}</small>" if period else ""}</div>'
                f'<ul>{lis}</ul>{_sbtn("Start with " + name, dest, "pill " + ("solid" if hl else "outline"))}</div>')
        return (f'<section class="pricing">{f"<p class=eyebrow>{E(b.eyebrow)}</p>" if b.eyebrow else ""}<h2>{E(b.title)}</h2>'
                f'<p class="lede">{E(b.text)}</p><div class="plans">{"".join(plans)}</div></section>')
    if t == "faq":
        qs = "".join(f'<details><summary>{E(q)}{_svg("chev")}</summary><p>{E(a)}</p></details>' for q, a in map(_split, b.items[:8]))
        return (f'<section class="faq">{f"<p class=eyebrow>{E(b.eyebrow)}</p>" if b.eyebrow else ""}<h2>{E(b.title)}</h2>{qs}</section>')
    if t == "cta":
        return (f'<section class="ctaband"><div>{f"<p class=eyebrow>{E(b.eyebrow)}</p>" if b.eyebrow else ""}<h2>{E(b.title)}</h2>'
                f'<p>{E(b.text)}</p></div><div>{_site_actions(b, ctx)}</div></section>')
    return None


def _auth_card(b, ctx):
    fields = []
    for x in b.items:
        parts = [p.strip() for p in x.split("|")]
        if parts[0].lower() == "link" and len(parts) >= 2:
            dest = ctx[0].by_name(ctx[1], parts[2]) if ctx and len(parts) > 2 else None
            fields.append(f'<span class="alink"{_goto(dest)}>{E(parts[1])}</span>')
            continue
        label, ph = parts[0], (parts[1] if len(parts) > 1 else parts[0])
        typ = "password" if "password" in label.lower() else ("email" if "email" in label.lower() else "text")
        fields.append(f'<div class="af"><label>{E(label)}</label><input type="{typ}" placeholder="{E(ph)}"></div>')
    primary = _sbtn(b.actions[0], _dest(ctx, b.targets, 0), "solid") if b.actions else ""
    switch = ""
    if len(b.actions) > 1:
        switch = f'<p class="switch">{E(b.note)} <span{_goto(_dest(ctx, b.targets, 1))}>{E(b.actions[1])}</span></p>'
    return (f'<div class="authwrap"><div class="auth"><h2>{E(b.title)}</h2><p class="sub">{E(b.text)}</p>'
            f'{"".join(fields)}{primary}{switch}</div></div>')


def site_page(state, screen, body_blocks, flow, ctx):
    name = state.selected_name or "Product"
    logo = state.brand.logo.svg if state.brand and state.brand.logo else ""
    mark = (f'<img alt="" onerror="this.remove()" src="data:image/svg+xml;charset=utf-8,{E(quote(logo))}">'
            if logo and logo.lstrip().startswith("<svg") else "")
    wm = f"{mark}{E(name)}"
    land, sin, sup = (flow.landing, flow.signin, flow.signup) if flow else (None, None, None)
    nav = (f'<nav class="snav"><span class="wm"{_goto(land)}>{wm}</span><div class="links">'
           f'<span class="hide-s"{_goto(land)}>Features</span><span class="hide-s"{_goto(land)}>Pricing</span><span class="hide-s"{_goto(land)}>About</span>'
           f'{_sbtn("Sign in", sin, "")}{_sbtn("Get started", sup, "solid")}</div></nav>')
    parts, loose = [], []

    def flush():
        if loose:
            parts.append(f'<div class="spad">{"".join(loose)}</div>')
            loose.clear()

    auth_done = False
    for b in body_blocks:
        if screen.layout == "auth" and b.type == "form" and not auth_done:
            flush()
            parts.append(_auth_card(b, ctx))
            auth_done = True
            continue
        sec = site_block(b, ctx)
        if sec is None:
            loose.append(block_html(b, ctx))
        else:
            flush()
            parts.append(sec)
    flush()
    tagline = state.brand.tagline if state.brand and state.brand.tagline else ""
    foot = (f'<footer class="sfoot"><div><div class="wm">{E(name)}</div><span>{E(tagline)}</span></div>'
            f'<div><b>Product</b><span{_goto(land)}>Features</span><span{_goto(land)}>Pricing</span><span>About</span></div>'
            f'<div><b>Support</b><span{_goto(sin)}>Sign in</span><span>Help centre</span><span>Privacy &amp; terms</span></div>'
            f'<div class="copy">© {E(name)}. All rights reserved.</div></footer>')
    return f'<div class="site">{nav}{"".join(parts)}{foot}</div>'
