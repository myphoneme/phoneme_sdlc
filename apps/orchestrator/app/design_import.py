"""
Bring your own designs (2026-10-10) -- Identity, Experience Blueprint.

The owner drops all their designs in one go: phone and web screenshots,
mockup boards with several screens on one image, a zip of images. GiveWings

  1. splits boards into single screens (device frames, then even gutters,
     then -- if neither works -- the vision model's own boxes),
  2. reads every screen with the vision model: phone or web, what kind of
     screen it is, the tab it sits under, the visible menu, colours, type,
  3. fills the blueprint draft from what it saw (platforms, phone tabs,
     web menu, landing sections, sign-in methods, look) and places each
     screen in the frame (landing, sign-in, sign-up, onboarding, Share
     sheet, web home, one per phone tab). Business screens (lists, detail,
     create, publish ...) are kept for the UI/UX stage, where they are
     matched to the frozen modules,
  4. reports coverage: frame slots without a design are generated in the
     style read off the designs, or the owner uploads one.

Low-confidence placements are marked "unsure" for the owner to confirm.
"""
import asyncio
import io
import json
import logging
import re
import uuid
import zipfile
from collections import Counter, deque
from pathlib import Path

from . import ai_router, blueprint, config, reqdoc, store
from .models import DesignAsset, DesignFile, DesignHints, GenerationItem, GenerationProgress, Palette

logger = logging.getLogger("phoneme.design_import")

KINDS = ("landing", "sign_in", "sign_up", "onboarding", "home", "list", "detail", "create", "publish",
         "settings", "profile", "share", "other")
FRAME_KINDS = {"landing": "landing", "sign_in": "sign_in", "sign_up": "sign_up", "onboarding": "onboarding", "share": "share"}
MAX_FILES, MAX_SCREENS, MAX_BYTES = 20, 30, 15 * 1024 * 1024
UNSURE_BELOW = 0.55
_tasks: set = set()


# ------------------------------------------------------------------ files
def folder(session_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", session_id):
        raise ValueError("bad session id")
    return config.UPLOAD_DIR / session_id / "designs"


def path_of(session_id: str, design_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{12}", design_id):
        raise ValueError("bad design id")
    return folder(session_id) / f"{design_id}.png"


def _image(data: bytes):
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.width * im.height > 60_000_000:
        raise ValueError("image too large")
    return im.convert("RGB")


def unpack(files: list[tuple[str, bytes]]) -> list[tuple[str, object, int]]:
    """(name, bytes) uploads -> (name, PIL image, upload index); zips are opened (images only)."""
    out = []
    for idx, (name, data) in enumerate(files):
        if data[:4] == b"PK\x03\x04":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist()[:60]:
                    if info.is_dir() or info.file_size > MAX_BYTES or not re.search(r"\.(png|jpe?g|webp|gif)$", info.filename, re.I):
                        continue
                    try:
                        out.append((Path(info.filename).name, _image(z.read(info)), idx))
                    except Exception:  # noqa: BLE001 -- skip unreadable members
                        continue
            continue
        try:
            out.append((name, _image(data), idx))
        except Exception:  # noqa: BLE001
            raise ValueError(f"{name}: not an image GiveWings can read (PNG, JPG, WebP, GIF or a zip of them)")
    return out


# ------------------------------------------------------------------ splitting
def _small(img, work=640):
    s = work / max(img.size)
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s)))), s


def device_frames(img) -> list[tuple]:
    """Phone mockups: a dark bezel ring around each screen."""
    g, s = _small(img.convert("L"))
    w, h = g.size
    px = g.load()
    dark = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if px[x, y] < 60:
                dark[y * w + x] = 1
    seen = bytearray(w * h)
    found = []
    for start in range(w * h):
        if not dark[start] or seen[start]:
            continue
        q = deque([start])
        seen[start] = 1
        x0 = x1 = start % w
        y0 = y1 = start // w
        n = 0
        while q:
            i = q.popleft()
            n += 1
            x, y = i % w, i // w
            x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
            for j in (i - 1 if x > 0 else -1, i + 1 if x < w - 1 else -1, i - w, i + w):
                if 0 <= j < w * h and dark[j] and not seen[j]:
                    seen[j] = 1
                    q.append(j)
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bh > 0.2 * h and 0.35 < bw / bh < 0.75 and n / (bw * bh) < 0.45:
            inset = max(2, int(bw * 0.035))
            found.append(tuple(int(v / s) for v in (x0 + inset, y0 + inset, x1 - inset, y1 - inset)))
    if len(found) == 1 and (found[0][2] - found[0][0]) * (found[0][3] - found[0][1]) > 0.6 * img.width * img.height:
        return []  # one frame filling the image: it's a single screen
    return found


def gutters(img) -> list[tuple]:
    """Boards laid out on a plain background: recursive cuts along empty rows/columns."""
    g, s = _small(img)
    w, h = g.size
    px = g.load()
    border = [px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)] + [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)]
    bg = Counter(tuple(c // 8 for c in p) for p in border).most_common(1)[0][0]
    bg = tuple(c * 8 + 4 for c in bg)

    def ink(x, y):
        p = px[x, y]
        return abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 36

    def cut(x0, y0, x1, y1, axis, depth):
        if depth > 4:
            return [(x0, y0, x1, y1)]
        span = range(x0, x1) if axis == 0 else range(y0, y1)
        other = (y1 - y0) if axis == 0 else (x1 - x0)
        thr = max(1, int(other * 0.004))
        prof = [sum(1 for t in (range(y0, y1) if axis == 0 else range(x0, x1)) if (ink(v, t) if axis == 0 else ink(t, v))) for v in span]
        segs, start, gap = [], None, 0
        min_gap = max(4, int(len(prof) * 0.015))
        for i, c in enumerate(prof):
            if c > thr:
                if start is None:
                    start = i
                gap = 0
            elif start is not None:
                gap += 1
                if gap >= min_gap:
                    segs.append((start, i - gap + 1))
                    start, gap = None, 0
        if start is not None:
            segs.append((start, len(prof) - gap))
        if len(segs) <= 1:
            if depth == 0 or axis == 0:
                return cut(x0, y0, x1, y1, 1 - axis, depth + 1) if axis == 0 else [(x0, y0, x1, y1)]
            return [(x0, y0, x1, y1)]
        out = []
        for a, b in segs:
            box = (x0 + a, y0, x0 + b, y1) if axis == 0 else (x0, y0 + a, x1, y0 + b)
            out += cut(*box, 1 - axis, depth + 1)
        return out

    boxes = cut(0, 0, w, h, 0, 0)
    area = w * h
    keep = [b for b in boxes if (b[2] - b[0]) * (b[3] - b[1]) > 0.04 * area and (b[3] - b[1]) > 0.15 * h]
    if len(keep) < 2:
        return []
    return [tuple(int(v / s) for v in b) for b in keep]


LAYOUT_PROMPT = """This image may be a single app/website screen, or a mockup board showing several screens side by side.
Return ONLY JSON: {"screens": [{"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}]} -- one box per separate screen as fractions
of the image width/height (x,y = top-left). Leave out logos, captions, colour swatches, photos and decoration.
If it is one screen, return a single box covering it."""


async def split(img) -> list[tuple]:
    boxes = device_frames(img) or gutters(img)
    if not boxes and max(img.size) > 1200:
        try:
            r = await ai_router.generate_vision(ai_router.Feature.DESIGN_VISION, LAYOUT_PROMPT, [("image/png", png(img, 1200))])
            d = reqdoc._extract_json(r["text"])
            for b in (d.get("screens") or [])[:12]:
                x, y, w, h = (float(b.get(k, 0)) for k in ("x", "y", "w", "h"))
                if w * h > 0.04 and w > 0.08 and h > 0.15:
                    boxes.append((int(x * img.width), int(y * img.height), int((x + w) * img.width), int((y + h) * img.height)))
        except Exception:  # noqa: BLE001 -- a failed layout read just means "one screen"
            boxes = []
        if len(boxes) < 2:
            boxes = []
    boxes.sort(key=lambda b: (round(b[1] / (img.height * 0.25)), b[0]))
    return boxes or [(0, 0, img.width, img.height)]


def png(img, longest=1400) -> bytes:
    if max(img.size) > longest:
        s = longest / max(img.size)
        img = img.resize((int(img.width * s), int(img.height * s)))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ------------------------------------------------------------------ reading a screen
def read_prompt(state) -> str:
    fonts = ", ".join(blueprint.FONTS)
    return (f'Product: {state.selected_name or "the product"} -- {state.concept_summary or ""}\n'
            "This image is ONE screen design (mockup or screenshot) the product owner wants. Read it and return ONLY JSON:\n"
            '{"is_screen": true, "platform": "phone|web", '
            '"kind": "landing|sign_in|sign_up|onboarding|home|list|detail|create|publish|settings|profile|share|other", '
            '"title": "<short screen name a user would say, e.g. Library>", '
            '"tab": "<the active bottom tab or menu item, or empty>", "tabs": ["<every tab-bar or main-menu label, in order>"], '
            '"nav": "tabs|sidebar|top|none", '
            '"landing_sections": ["hero|promise|features|download|pricing|faq|cta -- only for a public landing page, in order"], '
            '"sign_in_methods": ["email_password|email_otp|mobile_otp|google|apple|sso -- only on sign-in/sign-up screens"], '
            '"register_fields": ["<fields on a sign-up form>"], '
            '"colors": {"primary": "#hex", "ink": "#hex", "surface": "#hex", "accent": "#hex"}, '
            f'"heading_font": "<closest of: {fonts}>", "body_font": "<closest of the same list>", '
            '"radius": "sharp|rounded|soft", "density": "comfortable|compact", '
            '"description": "<one sentence: what the user does on this screen>", "confidence": 0.0}\n'
            "kind 'share' = the sheet another app opens to save something into this product. is_screen=false for logos, "
            "photos, colour swatches or anything that is not a screen. confidence = how sure you are of kind and platform.")


def _hex(v) -> str:
    v = str(v or "").strip()
    return v.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", v) else ""


async def read_screen(state, img) -> dict:
    r = await ai_router.generate_vision(ai_router.Feature.DESIGN_VISION, read_prompt(state), [("image/png", png(img))],
                                        system="You are a senior product designer cataloguing screen designs. JSON only.")
    d = reqdoc._extract_json(r["text"])
    if not isinstance(d, dict):
        raise ValueError("unreadable answer")
    return d


# ------------------------------------------------------------------ placing screens + filling the blueprint
def _slot_for(asset: DesignAsset, bp) -> str:
    if asset.kind in FRAME_KINDS:
        return FRAME_KINDS[asset.kind]
    if asset.platform == "web" and asset.kind == "home":
        return "web_home"
    if asset.platform == "phone" and bp.platforms != "web":
        tabs = {t.lower(): t for t in bp.mobile.tabs}
        if asset.tab and asset.tab.lower() in tabs and asset.kind in ("home", "list", "profile", "create", "settings"):
            return f"tab:{tabs[asset.tab.lower()]}"
        if asset.kind == "home" and bp.mobile.tabs:
            return f"tab:{bp.mobile.tabs[0]}"
    return ""


def place(bp) -> None:
    """(Re)assign frame slots: the first confident design per slot is placed;
    the rest are business screens, unless the owner already decided."""
    taken = set()
    for a in bp.designs:
        if a.status == "ignored":
            continue
        if a.status in ("placed", "unsure") and a.slot and a.confidence < 0 :  # owner-set (confidence -1)
            taken.add(a.slot)
    for a in bp.designs:
        if a.status == "ignored" or a.confidence < 0:
            continue
        slot = _slot_for(a, bp)
        if slot and slot not in taken:
            a.slot, a.status = slot, ("unsure" if a.confidence < UNSURE_BELOW else "placed")
            taken.add(slot)
        else:
            a.slot, a.status = "", ("unsure" if a.confidence < UNSURE_BELOW else "business")


def fill_blueprint(bp, reads: list[dict]) -> None:
    """Fill the draft blueprint from what the AI saw on the designs."""
    screens = [r for r in reads if r.get("is_screen", True)]
    if not screens:
        return
    phones = [r for r in screens if r.get("platform") == "phone"]
    webs = [r for r in screens if r.get("platform") == "web"]
    if phones and webs:
        bp.platforms, bp.primary = "both", ("mobile" if len(phones) >= len(webs) else "web")
    elif phones:
        bp.platforms, bp.primary = "mobile", "mobile"
    else:
        bp.platforms, bp.primary = "web", "web"
    if phones:
        tab_sets = Counter(tuple(t.strip() for t in (r.get("tabs") or []) if str(t).strip())[:5] for r in phones if r.get("nav") == "tabs")
        tab_sets.pop((), None)
        if tab_sets:
            bp.mobile.tabs = list(tab_sets.most_common(1)[0][0])
        if any(r.get("kind") == "share" for r in phones):
            bp.mobile.share_target = True
    if webs:
        navs = Counter(r.get("nav") for r in webs if r.get("nav") in ("sidebar", "top"))
        if navs:
            bp.web.nav = navs.most_common(1)[0][0]
    landing = next((r for r in screens if r.get("kind") == "landing"), None)
    if landing and landing.get("landing_sections"):
        bp.landing_sections = [s for s in landing["landing_sections"] if s in blueprint.SECTIONS]
        if "download" in bp.landing_sections and "Download app" not in bp.public_pages:
            bp.public_pages = bp.public_pages + ["Download app"]
    auth = [r for r in screens if r.get("kind") in ("sign_in", "sign_up")]
    methods = [m for r in auth for m in (r.get("sign_in_methods") or []) if m in blueprint.AUTH_METHODS]
    if methods:
        bp.auth.methods = list(dict.fromkeys(methods))
    fields = next((r.get("register_fields") for r in auth if r.get("kind") == "sign_up" and r.get("register_fields")), None)
    if fields:
        bp.auth.register_fields = [str(f) for f in fields][:6]
    for key, allowed in (("radius", blueprint.RADII), ("density", blueprint.DENSITIES),
                         ("heading_font", blueprint.FONTS), ("body_font", blueprint.FONTS)):
        votes = Counter(r.get(key) for r in screens if r.get(key) in allowed)
        if votes:
            setattr(bp.tokens, key, votes.most_common(1)[0][0])
    colors = {}
    for k in ("primary", "ink", "surface", "accent"):
        votes = Counter(_hex((r.get("colors") or {}).get(k)) for r in screens)
        votes.pop("", None)
        if votes:
            colors[k] = votes.most_common(1)[0][0]
    n_p, n_w = len(phones), len(webs)
    bp.design_hints = DesignHints(
        colors=colors, heading_font=bp.tokens.heading_font, body_font=bp.tokens.body_font,
        summary=f"Read {len(screens)} screen{'s' if len(screens) != 1 else ''} from your designs"
                + (f": {n_p} phone" if n_p else ":") + (" and" if n_p and n_w else "") + (f" {n_w} web" if n_w else "") + ".")


def required_slots(bp, name: str) -> list[tuple[str, str]]:
    out = [("landing", "Landing page"), ("sign_in", "Sign in")]
    if bp.auth.register_fields:
        out.append(("sign_up", "Create account"))
    if bp.auth.onboarding:
        out.append(("onboarding", "Welcome / first run"))
    if bp.platforms != "mobile":
        out.append(("web_home", "Web app home"))
    if bp.platforms != "web":
        out += [(f"tab:{t}", f"Phone tab · {t}") for t in bp.mobile.tabs]
        if bp.mobile.share_target:
            out.append(("share", f"Share to {name}"))
    return out


def coverage(state) -> dict:
    bp = state.brand.blueprint
    if not bp:
        return {"slots": [], "business": [], "unsure": [], "ignored": []}
    by_slot = {a.slot: a for a in bp.designs if a.slot and a.status in ("placed", "unsure")}
    slots = [{"slot": k, "label": label, "design_id": by_slot[k].design_id if k in by_slot else "",
              "status": by_slot[k].status if k in by_slot else "generate"} for k, label in required_slots(bp, state.selected_name or "the product")]
    return {
        "slots": slots,
        "business": [a.design_id for a in bp.designs if a.status == "business"],
        "unsure": [a.design_id for a in bp.designs if a.status == "unsure"],
        "ignored": [a.design_id for a in bp.designs if a.status == "ignored"],
        "palette_differs": bool(bp.design_hints.colors.get("primary")) and state.brand.palette is not None
        and bp.design_hints.colors["primary"].upper() != (state.brand.palette.primary or "").upper(),
    }


# ------------------------------------------------------------------ background run
def source_dir(session_id: str) -> Path:
    return folder(session_id) / "source"


def source_path(session_id: str, f: DesignFile) -> Path:
    return source_dir(session_id) / f"{f.file_id}.{f.ext}"


def _ext(name: str, data: bytes) -> str:
    if data[:4] == b"PK\x03\x04":
        return "zip"
    m = re.search(r"\.(png|jpe?g|webp|gif)$", name or "", re.I)
    return (m.group(1).lower().replace("jpeg", "jpg") if m else "png")


async def start(session_id: str, files: list[tuple[str, bytes]]) -> None:
    """Keep every upload as-is in the product's design folder, split it into
    screens now (fast) and read the screens in the background."""
    state = await store.get_session(session_id)
    images = unpack(files)
    if not images:
        raise ValueError("no images found in the upload")
    d = folder(session_id)
    d.mkdir(parents=True, exist_ok=True)
    src = source_dir(session_id)
    src.mkdir(parents=True, exist_ok=True)
    bp = state.brand.blueprint
    records = []
    for name, data in files:
        f = DesignFile(file_id=uuid.uuid4().hex[:12], name=(name or "design")[:120], size=len(data), ext=_ext(name, data), uploaded_at=_now())
        records.append(f)
    new = []
    for name, img, idx in images:
        for box in await split(img):
            if len(new) + len(bp.designs) >= MAX_SCREENS:
                break
            crop = img.crop(box)
            did = uuid.uuid4().hex[:12]
            (d / f"{did}.png").write_bytes(png(crop, 1600))
            new.append(DesignAsset(design_id=did, original=name, width=crop.width, height=crop.height, status="unsure",
                                   title=Path(name).stem[:60], file_id=records[idx].file_id))
            records[idx].screens += 1
    if not new:
        raise ValueError(f"at most {MAX_SCREENS} designs per product — remove some first")
    for (name, data), f in zip(files, records):
        if f.screens:
            source_path(session_id, f).write_bytes(data)
            bp.design_files.append(f)
    bp.designs += new
    state.design_import = GenerationProgress(
        status="running", total=len(new), done=0, started_at=_now(), updated_at=_now(),
        items=[GenerationItem(module=a.original, req_id=a.design_id) for a in new])
    await store.save_session(state)
    t = asyncio.create_task(_read_all(session_id, [a.design_id for a in new]))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def _read_all(session_id: str, ids: list[str]) -> None:
    from PIL import Image
    sem = asyncio.Semaphore(4)
    state = await store.get_session(session_id)
    reads: dict[str, dict] = {}
    errors: dict[str, str] = {}

    async def one(did):
        async with sem:
            try:
                img = Image.open(path_of(session_id, did)).convert("RGB")
                reads[did] = await read_screen(state, img)
            except Exception as exc:  # noqa: BLE001
                logger.warning("design %s could not be read: %s", did, exc)
                errors[did] = f"{type(exc).__name__}: {str(exc)[:160]}"
    await asyncio.gather(*(one(d) for d in ids))

    state = await store.get_session(session_id)
    bp = state.brand.blueprint
    for a in bp.designs:
        if a.design_id in reads:
            r = reads[a.design_id]
            a.platform = r.get("platform") if r.get("platform") in ("phone", "web") else ("phone" if a.height > a.width * 1.3 else "web")
            a.kind = r.get("kind") if r.get("kind") in KINDS else "other"
            a.title = str(r.get("title") or a.title)[:60]
            a.tab = str(r.get("tab") or "")[:30]
            a.description = str(r.get("description") or "")[:240]
            try:
                a.confidence = max(0.0, min(1.0, float(r.get("confidence", 0.5))))
            except (TypeError, ValueError):
                a.confidence = 0.5
            if r.get("is_screen") is False:
                a.status = "ignored"
            a.read = {k: r[k] for k in ("platform", "kind", "tab", "tabs", "nav", "landing_sections", "sign_in_methods", "register_fields",
                                        "colors", "heading_font", "body_font", "radius", "density", "is_screen") if k in r}
        elif a.design_id in errors:
            a.platform = "phone" if a.height > a.width * 1.3 else "web"
            a.description = "Could not be read automatically — sort it yourself."
            a.confidence = 0.0
    if not bp.frozen:
        all_reads = [{**(reads.get(a.design_id) or a.read), "platform": a.platform, "kind": a.kind}
                     for a in bp.designs if (a.design_id in reads or a.read) and a.status != "ignored"]
        fill_blueprint(bp, all_reads)
        state.brand.blueprint = blueprint.normalise(bp)
        bp = state.brand.blueprint
    place(bp)
    offer_palette(state)
    g = state.design_import
    for it in g.items:
        it.status = "failed" if it.req_id in errors else "done"
        it.error = errors.get(it.req_id, "")
    g.done = len(g.items)
    g.status = "failed" if errors and len(errors) == len(g.items) else "done"
    g.updated_at = _now()
    await store.save_session(state)


def update(state, req) -> None:
    """The owner corrects the sort (their choice is final: confidence -1)."""
    bp = state.brand.blueprint
    a = next((x for x in bp.designs if x.design_id == req.design_id), None)
    if not a:
        raise KeyError("design not found")
    if req.platform in ("phone", "web"):
        a.platform = req.platform
    if req.kind in KINDS:
        a.kind = req.kind
    if req.title is not None and req.title.strip():
        a.title = req.title.strip()[:60]
    if req.status in ("placed", "business", "ignored", "unsure"):
        a.status = req.status
    if req.slot is not None:
        slot = req.slot.strip()
        valid = {k for k, _ in required_slots(bp, state.selected_name or "")}
        if slot and slot not in valid:
            raise ValueError("that place is not in the frame")
        for other in bp.designs:  # one design per frame slot
            if slot and other is not a and other.slot == slot:
                other.slot, other.status = "", "business"
        a.slot = slot
        a.status = "placed" if slot else (req.status if req.status in ("business", "ignored") else "business")
    elif req.status == "placed" and not a.slot:
        a.status = "business"
    a.confidence = -1.0  # decided by the owner


# ------------------------------------------------------------------ step 2: match screens to the frozen modules (UI/UX)
def _words(t: str) -> set:
    return set(re.findall(r"[a-z]{3,}", (t or "").lower()))


def decidable(state, m) -> bool:
    """Modules the owner's designs can belong to. The sign-in/profile/admin
    modules are GiveWings standard modules and the account module follows the
    frame, so they never wait for a design."""
    from . import site_kit
    spec = next((x for x in state.module_specs if x.name == m.module), None)
    return not (site_kit.is_account(state, m.module) or (spec and spec.kind == "standard"))


def _module_text(state, m) -> str:
    spec = next((x for x in state.module_specs if x.name == m.module), None)
    return f"{m.module}. {(spec.description if spec else '') or m.title}"


def heuristic(a: DesignAsset, mods: list[tuple[str, str]]) -> tuple[str, float]:
    aw = _words(f"{a.title} {a.tab} {a.description} {a.kind.replace('_', ' ')}")
    best, score = "", 0
    for name, text in mods:
        sc = len(aw & _words(name)) * 2 + len(aw & _words(text))
        if sc > score:
            best, score = name, sc
    return (best, min(0.5, 0.15 * score)) if best else ("", 0.0)


async def match(state) -> int:
    """Propose a module for every business screen the owner has not decided."""
    bp = state.brand.blueprint
    mods = [(m.module, _module_text(state, m)) for m in state.ui_modules if decidable(state, m)]
    todo = [a for a in bp.designs if a.status == "business" and a.module_conf != -1 and not a.applied]
    if not todo or not mods:
        return 0
    for a in todo:
        a.module, a.module_conf = heuristic(a, mods)
    names = {n for n, _ in mods}
    prompt = (
        f"Product: {state.selected_name}. The owner's own screen designs must be matched to the product's modules.\n\n"
        "Modules:\n" + "\n".join(f"- {n}: {t[:240]}" for n, t in mods) + "\n\nScreens:\n"
        + "\n".join(f"- {a.design_id} ({a.platform}, {a.kind}{', tab ' + a.tab if a.tab else ''}): {a.title}. {a.description}" for a in todo)
        + '\n\nMatch each screen to the ONE module it belongs to, or "" when it fits none. '
        'Answer JSON only: {"matches":[{"design_id":"..","module":"<exact module name or empty>","confidence":0.0-1.0}]}'
    )
    try:
        r = await ai_router.generate(ai_router.Feature.TECH_DESIGN_GENERATION, prompt,
                                     system="You are a product analyst matching screen designs to modules. JSON only.")
        d = reqdoc._extract_json(r["text"])
        for x in (d.get("matches") if isinstance(d, dict) else []) or []:
            a = next((t for t in todo if t.design_id == str(x.get("design_id", ""))), None)
            mod = str(x.get("module") or "")
            if a and (mod in names or not mod):
                try:
                    conf = max(0.0, min(1.0, float(x.get("confidence", 0.6))))
                except (TypeError, ValueError):
                    conf = 0.6
                a.module, a.module_conf = mod, (conf if mod else 0.0)
    except Exception as e:  # the heuristic proposal stands; the owner checks it anyway
        logger.warning("design match fell back to keywords: %s", e)
    return len(todo)


def assign(state, design_id: str, module: str) -> None:
    bp = state.brand.blueprint
    a = next((x for x in bp.designs if x.design_id == design_id), None)
    if not a:
        raise KeyError("design not found")
    if a.applied:
        raise ValueError("this design is already inside a module -- remove that screen there first")
    if module and not any(m.module == module and decidable(state, m) for m in state.ui_modules):
        raise ValueError("that module does not take designs")
    a.module, a.module_conf = module, -1.0
    if a.status == "ignored":
        a.status = "business"


def module_board(state) -> dict:
    """What the owner checks at UI/UX: each module with its screens, the loose
    ones, and which modules still need a decision."""
    bp = state.brand.blueprint
    if not bp or not any(a.status != "ignored" for a in bp.designs):
        return {"active": False, "modules": [], "loose": [], "pending_apply": 0, "blocked": None}
    live = [a for a in bp.designs if a.status == "business"]
    mods = []
    for m in state.ui_modules:
        if not decidable(state, m):
            continue
        ups = [s for s in (m.doc.screens if m.doc else []) if s.source == "upload"]
        mine = [a for a in live if a.module == m.module]
        mods.append({"ui_id": m.ui_id, "module": m.module, "frozen": m.status == "Frozen",
                     "designs": [a.design_id for a in mine if not a.applied], "applied": [a.design_id for a in mine if a.applied],
                     "uploads": len(ups), "generate_ok": m.generate_ok,
                     "state": "yours" if (ups or mine) else ("generate" if m.generate_ok else "decide")})
    out = {"active": True, "modules": mods, "loose": [a.design_id for a in live if not a.module],
           "pending_apply": sum(1 for a in live if a.module and not a.applied)}
    out["blocked"] = _blocked(out)
    return out


def gaps(state) -> list[str]:
    return [s["label"] for s in coverage(state)["slots"] if s["status"] == "generate"]


def identity_gate(state) -> str | None:
    """Empty places in the frame need an answer: upload, or agree to generate."""
    bp = state.brand.blueprint
    if not bp or not any(a.status != "ignored" for a in bp.designs) or bp.design_hints.generate_ok:
        return None
    g = gaps(state)
    if g:
        return (f"{len(g)} place{'s' if len(g) != 1 else ''} in the frame have no design ({', '.join(g[:4])}{'…' if len(g) > 4 else ''}). "
                "Upload them, or choose \"Generate them in my style\" -- then freeze.")
    return None


def module_gate(state) -> str | None:
    return module_board(state)["blocked"]


def _blocked(b: dict) -> str | None:
    if b["loose"]:
        return f"{len(b['loose'])} of your screens are not matched to a module -- assign each one, or mark it \"not a screen\"."
    if b["pending_apply"]:
        return "Add your matched designs to their modules (button on the design board) before the baseline."
    need = [m["module"] for m in b["modules"] if m["state"] == "decide"]
    if need:
        return "Decide for " + ", ".join(need[:4]) + (f" and {len(need) - 4} more" if len(need) > 4 else "") + ": upload your design, or let GiveWings generate it in your style."
    return None


def style_text(state) -> str:
    """The look read off the owner's designs, handed to every generation prompt."""
    bp = state.brand.blueprint if state.brand else None
    if not bp or not any(a.status != "ignored" for a in bp.designs):
        return ""
    h = bp.design_hints
    bits = [h.summary] if h.summary else []
    if h.colors:
        bits.append("colours " + ", ".join(f"{k} {v}" for k, v in h.colors.items() if v))
    if h.heading_font or h.body_font:
        bits.append(f"type {h.heading_font or '-'} / {h.body_font or '-'}")
    bits.append(f"corners {bp.tokens.radius}, spacing {bp.tokens.density}")
    done = [a.title for a in bp.designs if a.status in ("placed", "business") and a.title][:12]
    if done:
        bits.append("the owner's own screens already exist for: " + "; ".join(done))
    return "The owner supplied their own designs. Generate anything missing in that same look -- " + "; ".join(bits) + "."


# ------------------------------------------------------------------ colours from the designs (2026-10-13)
def _hsl(rgb):
    import colorsys
    r, g, b = (v / 255 for v in rgb)
    h, lt, sat = colorsys.rgb_to_hls(r, g, b)
    return h * 360, sat, lt


def pixel_palette(paths: list[Path]) -> dict:
    """Dominant colours of the screens themselves: the most used saturated
    colour is the brand primary, the most used light one the background, the
    most used dark one the text, and a second saturated hue the accent."""
    from PIL import Image
    counts: Counter = Counter()
    for p in paths[:20]:
        try:
            im = Image.open(p).convert("RGB")
        except Exception:  # noqa: BLE001
            continue
        im.thumbnail((96, 96))
        q = im.quantize(colors=10, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette()
        for n, i in q.getcolors() or []:
            counts[tuple(pal[i * 3:i * 3 + 3])] += n
    if not counts:
        return {}
    hexs = lambda c: "#" + "".join(f"{v:02X}" for v in c)  # noqa: E731
    sat = [(n, c) for c, n in counts.items() if _hsl(c)[1] > 0.35 and 0.18 < _hsl(c)[2] < 0.78]
    light = [(n, c) for c, n in counts.items() if _hsl(c)[2] > 0.86]
    dark = [(n, c) for c, n in counts.items() if _hsl(c)[2] < 0.22]
    out = {}
    if sat:
        sat.sort(reverse=True)
        out["primary"] = hexs(sat[0][1])
        h0 = _hsl(sat[0][1])[0]
        acc = next((c for n, c in sat[1:] if min(abs(_hsl(c)[0] - h0), 360 - abs(_hsl(c)[0] - h0)) > 40), None)
        if acc:
            out["accent"] = hexs(acc)
    if light:
        out["surface"] = hexs(max(light)[1])
    if dark:
        out["ink"] = hexs(max(dark)[1])
    return out


def design_palette(state) -> Palette | None:
    """A palette made from the owner's designs: what the AI read off the
    screens, completed by their dominant pixel colours."""
    bp = state.brand.blueprint
    live = [a for a in bp.designs if a.status != "ignored"] if bp else []
    if not live:
        return None
    px = pixel_palette([path_of(state.session_id, a.design_id) for a in live])
    seen = bp.design_hints.colors or {}
    c = {k: seen.get(k) or px.get(k) for k in ("primary", "ink", "surface", "accent")}
    if not c["primary"]:
        return None
    from .brand import contrast, _mix
    c["ink"] = c["ink"] or "#15151B"
    c["surface"] = c["surface"] or _mix("#FFFFFF", c["primary"], 0.06)
    if contrast(c["ink"], c["surface"]) < 4.5:
        c["ink"] = "#15151B"
    c["accent"] = c["accent"] or _mix(c["primary"], "#000000", 0.25)
    return Palette(name="From your designs", mood="Read from your uploads",
                   rationale=f"Taken from {len(live)} uploaded screen{'s' if len(live) != 1 else ''}: the brand colour, text, background and accent they use.",
                   **c)


def offer_palette(state, apply: bool = True) -> None:
    """Put the designs' palette first among the options and make it the
    default -- unless Colours is frozen or the owner tuned a palette by hand."""
    p = design_palette(state)
    b = state.brand
    b.palette_options = [x for x in b.palette_options if x.name != "From your designs"]
    if not p:
        return
    b.palette_options.insert(0, p)
    if not apply:
        return
    from . import brand
    try:
        brand.check_edit(state, "colours")
    except ValueError:
        return
    if not b.palette or not b.palette.name.endswith("(edited)"):
        b.palette = p
        state.selected_theme = p.name


# ------------------------------------------------------------------ managing the uploaded files (2026-10-13)
def files_view(state) -> list[dict]:
    """Every uploaded file with its screens; designs uploaded before files
    were kept appear grouped by their original name."""
    bp = state.brand.blueprint
    if not bp:
        return []
    out = []
    for f in bp.design_files:
        ids = [a.design_id for a in bp.designs if a.file_id == f.file_id]
        out.append({**f.model_dump(), "screens": len(ids), "design_ids": ids, "kept": True})
    legacy = {}
    for a in bp.designs:
        if not a.file_id:
            legacy.setdefault(a.original or "earlier upload", []).append(a.design_id)
    for name, ids in legacy.items():
        out.append({"file_id": "legacy-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40], "name": name, "size": 0, "ext": "",
                    "uploaded_at": "", "screens": len(ids), "design_ids": ids, "kept": False})
    return out


def _file_ids(state, file_id: str) -> list[str]:
    for f in files_view(state):
        if f["file_id"] == file_id:
            return f["design_ids"]
    raise KeyError("file not found")


def remove_file(state, file_id: str) -> int:
    """Remove an uploaded file and every screen taken from it. Screens already
    added to a UI/UX module stay there (they are copies)."""
    bp = state.brand.blueprint
    ids = set(_file_ids(state, file_id))
    for did in ids:
        try:
            path_of(state.session_id, did).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
    bp.designs = [a for a in bp.designs if a.design_id not in ids]
    keep = []
    for f in bp.design_files:
        if f.file_id == file_id:
            try:
                source_path(state.session_id, f).unlink(missing_ok=True)
            except OSError:
                pass
        else:
            keep.append(f)
    bp.design_files = keep
    place(bp)
    if not bp.designs:
        bp.design_hints = DesignHints(generate_ok=bp.design_hints.generate_ok)
    offer_palette(state)
    return len(ids)


async def reread_file(session_id: str, file_id: str) -> None:
    state = await store.get_session(session_id)
    ids = _file_ids(state, file_id)
    for a in state.brand.blueprint.designs:
        if a.design_id in ids and a.confidence >= 0:
            a.status = "unsure"
    state.design_import = GenerationProgress(
        status="running", total=len(ids), done=0, started_at=_now(), updated_at=_now(),
        items=[GenerationItem(module=file_id, req_id=d) for d in ids])
    await store.save_session(state)
    t = asyncio.create_task(_read_all(session_id, ids))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
