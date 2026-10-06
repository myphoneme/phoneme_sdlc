"""
GiveWings public-site kit (2026-10-06).

Every product ships with the standard Sign-in & Account module, and every
commercial product needs a front door. This kit gives that module a
consistent, modern public site in the product's own brand:

  Landing page  -> hero, promise strip, "how it works" steps, plans, FAQ,
                   closing call-to-action
  Create account -> centred auth card (name, email, password)
  Sign in        -> centred auth card (email, password)

Copy the AI wrote for the landing page (hero / promise / faq / pricing /
cta blocks) is kept; anything missing is filled from facts already agreed
in the journey (tagline, concept brief, module outcomes, access rules), so
the page never shows invented claims. Other screens the AI drew for the
module (verify code, forgot password ...) stay after the kit screens.
"""
import re

from .models import UIBlock, UIDoc, UIScreen

LANDING, REGISTER, SIGNIN, ONBOARD = "Landing page", "Create account", "Sign in", "Welcome"
_LANDING_RE = re.compile(r"\b(landing|welcome|home ?page|marketing)\b", re.I)
_REGISTER_RE = re.compile(r"\b(sign[ -]?up|register|create (an )?account|get started)\b", re.I)
_SIGNIN_RE = re.compile(r"\b(sign[ -]?in|log[ -]?in)\b", re.I)


def is_account(state, module_name: str) -> bool:
    spec = next((m for m in state.module_specs if m.name == module_name), None)
    return bool(spec and spec.standard_key == "account") or module_name.lower().startswith("sign-in")


def _home_module(state) -> str:
    """First business module = where a signed-in user lands."""
    biz = [m for m in state.module_specs if m.kind != "standard"]
    return biz[0].name if biz else ""


def _first_sentence(s: str, limit: int = 220) -> str:
    s = (s or "").strip()
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    out = m.group(1) if m else s
    return out if len(out) <= limit else out[: limit - 1].rsplit(" ", 1)[0] + "…"


def _short(s: str, words: int = 9) -> str:
    w = (s or "").strip().rstrip(".").split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def landing_blocks(state, ai_blocks: list[UIBlock], bp=None) -> list[UIBlock]:
    name = state.selected_name or "Product"
    brand = state.brand
    tagline = (brand.tagline if brand and brand.tagline else "").strip()
    brief = state.concept_brief
    by_type = {}
    for b in ai_blocks:
        by_type.setdefault(b.type, b)

    hero = by_type.get("hero") or by_type.get("header")
    hero = UIBlock(
        type="hero",
        eyebrow=(hero.eyebrow if hero and hero.eyebrow else ""),
        title=(hero.title if hero and hero.title else tagline or name),
        text=(hero.text if hero and hero.text else _first_sentence((brief.summary if brief else "") or state.concept_summary)),
        items=(hero.items if hero and hero.type == "hero" and hero.items else
               [f"{m.name} — {_short(m.outcome or m.description, 7)}" for m in state.module_specs if m.kind != "standard"][:3]),
        actions=["Get started free", "See how it works"], targets=[REGISTER, "#how"],
    )
    if not hero.eyebrow:
        who = (brief.target_users if brief else "").strip().rstrip(".")
        hero.eyebrow = f"Built for {' '.join(who.split()[:4]).lower()}" if who else name

    promise = by_type.get("promise")
    if not promise or not promise.items:
        items = [_short(x, 8) for x in (brief.must_haves if brief else [])][:3]
        standard = ["Your data stays yours, to download or delete",
                    "Sign in once, pick up on any device",
                    "Security and health monitoring built in"]
        items = (items + standard)[:3]
        promise = UIBlock(type="promise", eyebrow=f"The {name} promise", items=items)

    biz = [m for m in state.module_specs if m.kind != "standard"]
    steps = [f"{m.name} — {m.outcome or _first_sentence(m.description, 160)}" for m in biz][:4]
    if not steps:  # before Freeze Scope: what the concept already promises
        steps = [f"{_short(x, 5)} — {x}" for x in (brief.must_haves if brief else [])][:3] or [
            "Sign up in a minute — create your account and you're in",
            f"Do the core job — {_short(tagline or (brief.core_workflow if brief else '') or 'the main task, done in one place', 10)}",
            "See the outcome — results you can share, revisit and act on"]
    ai_feat = by_type.get("features") or by_type.get("cards")
    features = UIBlock(
        type="features", eyebrow=(ai_feat.eyebrow if ai_feat and ai_feat.eyebrow else "How it works"),
        title=(ai_feat.title if ai_feat and ai_feat.type == "features" and ai_feat.title else f"From first step to outcome with {name}."),
        text=(ai_feat.text if ai_feat and ai_feat.type == "features" and ai_feat.text else tagline),
        items=(ai_feat.items if ai_feat and ai_feat.type == "features" and ai_feat.items else steps or (ai_feat.items if ai_feat else [])),
    )

    public = [m for m in state.module_specs if m.access in ("public", "mixed")]
    pricing = by_type.get("pricing")
    if not pricing or not pricing.rows:
        trial = "; ".join(f"{m.name}{' — ' + m.access_note if m.access_note else ''}" for m in public) or "Explore the public pages"
        full = "; ".join(m.name for m in biz) or "Every feature"
        pricing = UIBlock(
            type="pricing", eyebrow="Plans", title="Start free, upgrade when it sticks.",
            text="Plan names and prices are placeholders until the commercial model is confirmed.",
            rows=[["Trial", "Free", "", "Try it before you sign up.", trial, ""],
                  ["Full access", "Set at launch", "", f"Everything {name} does, once you have an account.", full, "Most popular"]],
        )

    faq = by_type.get("faq")
    if not faq or not faq.items:
        trial_q = ("Can I try it without an account? — Yes: " + ", ".join(m.name for m in public) + " can be used without signing in."
                   if public else "Do I need an account? — Yes. Sign up takes a minute and a one-time code confirms it is you.")
        faq = UIBlock(type="faq", eyebrow="Before you start", title="A few useful answers", items=[
            trial_q,
            "How do I sign in? — With your email or mobile number; a one-time code confirms new accounts.",
            "Can I take my data with me? — Yes. Download a copy or delete your account from Settings at any time.",
            "Is my account secure? — Repeated failed sign-ins lock the account and you are notified straight away.",
        ])

    cta = by_type.get("cta")
    cta = UIBlock(type="cta", eyebrow=(cta.eyebrow if cta and cta.eyebrow else "Get started"),
                  title=(cta.title if cta and cta.title else (tagline or f"Start with {name} today.")),
                  text=(cta.text if cta and cta.text else _first_sentence((brief.target_users if brief else "") or "")),
                  actions=["Get started free"], targets=[REGISTER])
    download = by_type.get("download") or UIBlock(
        type="download", eyebrow="Get the app", title=f"{name} in your pocket.",
        text="Scan the code with your phone camera to install it for iPhone or Android, or keep using the web.",
        items=["App Store", "Google Play"])
    blocks = {"hero": hero, "promise": promise, "features": features, "download": download, "pricing": pricing, "faq": faq, "cta": cta}
    order = bp.landing_sections if bp and bp.landing_sections else ["hero", "promise", "features", "pricing", "faq", "cta"]
    return [blocks[k] for k in order if k in blocks]


_PLACEHOLDER = {"name": "Your name", "full name": "Your name", "email": "you@example.com", "work email": "you@company.com",
                "password": "Choose a password", "mobile number": "+91 98765 43210", "mobile": "+91 98765 43210",
                "username": "@yourname", "company": "Company name"}
_SOCIAL = {"google": "Continue with Google", "apple": "Continue with Apple", "sso": "Continue with company SSO"}


def _auth_forms(bp, verify, home, forgot, onboarding):
    """Register and sign-in form blocks shaped by the blueprint's sign-in choice."""
    methods = bp.auth.methods if bp else ["email_password"]
    fields = bp.auth.register_fields if bp else ["Name", "Email", "Password"]
    social = [f"social|{_SOCIAL[m]}" for m in methods if m in _SOCIAL]
    reg_items = [f"{f}|{_PLACEHOLDER.get(f.lower(), f)}" for f in fields]
    if "mobile_otp" in methods and "email_password" not in methods:
        sin_items, sin_btn, sub = ["Mobile number|+91 98765 43210"], "Send me a code", "We'll text you a one-time code"
    elif "email_otp" in methods and "email_password" not in methods:
        sin_items, sin_btn, sub = ["Email|you@example.com"], "Email me a code", "We'll email you a one-time sign-in code"
    else:
        sin_items, sin_btn, sub = ["Email|you@example.com", "Password|Your password"], "Sign in", "Enter your email and password to sign in"
        if forgot:
            sin_items.append(f"link|Forgot password?|{forgot}")
    after_reg = onboarding or verify or home
    register = UIBlock(type="form", title="Get started", text="Create an account to get started", items=reg_items + social,
                       note="Already have an account?", actions=["Get started", "Sign in"], targets=[after_reg, SIGNIN])
    signin = UIBlock(type="form", title="Sign in", text=sub, items=sin_items + social,
                     note="Don't have an account?", actions=[sin_btn, "Get started"], targets=[verify if "code" in sin_btn else home, REGISTER])
    return register, signin


def apply(state, doc: UIDoc, bp=None, home: str | None = None) -> UIDoc:
    """Rebuild the Sign-in & Account screen set around the kit screens,
    shaped by the Experience Blueprint when one exists."""
    if bp is None and state.brand:
        bp = state.brand.blueprint
    ai_landing, rest = None, []
    for s in doc.screens:
        n = s.name
        other = re.search(r"verif|code|otp|forgot|reset|recover|terms|privacy|password|2fa|post-?auth|redirect|silent|session|sso", n, re.I)
        replaced = s.source == "kit" or (s.source != "upload" and not other and (_LANDING_RE.search(n) or _REGISTER_RE.search(n) or _SIGNIN_RE.search(n)))
        if not replaced:
            rest.append(s)
        elif (s.source == "kit" and n == LANDING) or (s.source != "kit" and _LANDING_RE.search(n)):
            ai_landing = ai_landing or s
    verify = next((s.name for s in rest if re.search(r"verif|code|otp", s.name, re.I)), "")
    home = home or _home_module(state)
    forgot = next((s.name for s in rest if re.search(r"forgot|reset|recover", s.name, re.I)), "")
    onboarding = ONBOARD if bp and bp.auth.onboarding else ""
    register, signin = _auth_forms(bp, verify, home, forgot, onboarding)
    mobile_first = bool(bp and bp.primary == "mobile")
    kit = [
        UIScreen(screen_id="K1", name=LANDING, purpose="Visitors learn what the product does and start a free account.",
                 route="/", layout="public", source="kit", blocks=landing_blocks(state, ai_landing.blocks if ai_landing else [], bp),
                 states=["Signed-in visitors see 'Open app' instead of 'Get started'"]),
        UIScreen(screen_id="K2", name=REGISTER, purpose="A visitor creates an account.", route="/sign-up", layout="auth", source="kit",
                 blocks=[register], states=["Already registered: offer Sign in", "Invalid entry: explain the rule inline"]),
        UIScreen(screen_id="K3", name=SIGNIN, purpose="A returning user signs in.", route="/sign-in", layout="auth", source="kit",
                 blocks=[signin], states=["Wrong details: generic error, no hint which field", "Locked after repeated failures: explain and offer reset"]),
    ]
    if onboarding:
        kit.append(UIScreen(screen_id="K4", name=ONBOARD, purpose="First-run steps right after sign-up.", route="/welcome",
                            layout="mobile" if mobile_first else "app", source="kit",
                            blocks=[UIBlock(type="header", title=f"Welcome to {state.selected_name or 'the product'}",
                                            text="A few quick steps and you're ready."),
                                    UIBlock(type="steps", items=bp.auth.onboarding),
                                    UIBlock(type="buttons", actions=["Continue", "Skip for now"], targets=[home, home])]))
    return doc.model_copy(update={"screens": kit + rest})
