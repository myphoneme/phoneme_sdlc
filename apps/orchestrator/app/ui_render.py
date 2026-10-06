"""
Server-side renderer for UI/UX screen specs (2026-10-04).

Follows Phoneme's UI/UX mockup system: one page, brand palette as CSS
custom properties, a step nav numbered to match the BRD/PRD modules, and
one .section per screen with a browser-chrome .frame. The same HTML is
shown in the portal (iframe) and downloaded as the mockup deliverable, so
what is reviewed is exactly what is exported.
"""
import html

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
        self.signin = next((k for name, k in self.first_of.items() if name.lower().startswith("sign-in")), None)

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
    body = "".join(block_html(b, ctx) for b in screen.blocks)
    url = f"{domain}{screen.route or '/'}"
    name = E(state.selected_name or "Product")
    if screen.layout == "image":
        inner = f'<div class="content image-content">{body}</div>'
    elif screen.layout == "public":
        inner = f'<div class="pubnav"><b>{name}</b><div><span>Features</span><span>Pricing</span><span class="btn btn-primary" style="margin-left:18px"{_goto(flow.signin if flow else None)}>Sign in</span></div></div><div class="content">{body}</div>'
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
    }
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
    mark = f'<img alt="" style="height:44px" src="data:image/svg+xml;utf8,{html.escape(logo)}">' if logo else f'<span class="brand-mark">{E((state.selected_name or "P")[:1])}</span>'
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{E(state.selected_name)} — {E(title_suffix)}</title>"
        "<link rel=preconnect href=https://fonts.googleapis.com><link href='https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Manrope:wght@700;800&display=swap' rel=stylesheet>"
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
    }
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
        "<link href='https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Manrope:wght@700;800&display=swap' rel=stylesheet>"
        f"<style>{css}{PROTO_CSS}</style></head><body>"
        f'<div class="proto-bar"><b>{E(state.selected_name)}</b><button id="pPrev">← Previous</button>'
        f'<select id="pSel" aria-label="Jump to screen">{"".join(opts)}</select><button id="pNext" class="primary">Next →</button>'
        f'<span class="pos" id="pPos"></span><label><input type="checkbox" id="pHl"> Highlight clickable areas</label></div>'
        f"{body}<script>{PROTO_JS}</script></body></html>"
    )
