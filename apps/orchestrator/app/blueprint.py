"""
Experience Blueprint (2026-10-07).

The portal's structure and look -- platforms, public pages, landing
sections, sign-in, web and mobile app frames, typography -- chosen at the
Identity stage from a template, edited by the owner, previewed as a
clickable branded skeleton and frozen with the brand. The UI/UX stage then
draws module screens inside this frame instead of inventing it.
"""
import re
from datetime import datetime, timezone

from .models import (AuthSpec, ExperienceBlueprint, ExperienceTokens, MobileShell, UIBlock, UIDoc, UIModule,
                     UIScreen, WebShell)

PLATFORMS = ("web", "mobile", "both")
RADII = ("sharp", "rounded", "soft")
DENSITIES = ("comfortable", "compact")
NAVS = ("sidebar", "top")
HOMES = ("dashboard", "feed", "inbox")
SECTIONS = ("hero", "promise", "features", "download", "pricing", "faq", "cta")
PAGES = ("Landing", "Pricing", "About", "Blog", "Contact", "Download app")
AUTH_METHODS = {
    "email_password": "Email & password", "email_otp": "Email one-time code", "mobile_otp": "Mobile one-time code",
    "google": "Continue with Google", "apple": "Continue with Apple", "sso": "Company single sign-on (SSO)",
}
FONTS = ("Space Grotesk", "IBM Plex Sans", "Inter", "Manrope", "DM Sans", "Plus Jakarta Sans", "Outfit",
         "Poppins", "Nunito Sans", "Source Sans 3", "Lora", "Fraunces")

TEMPLATES = {
    "saas": {
        "name": "SaaS Launch",
        "summary": "Marketing site with plans and FAQ, then a sidebar web app. Best for B2B and prosumer tools sold on subscription.",
        "fits": "Web apps sold by subscription",
        "bp": dict(platforms="web", primary="web",
                   tokens=dict(heading_font="Space Grotesk", body_font="IBM Plex Sans", radius="rounded", density="comfortable"),
                   public_pages=["Landing", "Pricing", "About"], landing_sections=["hero", "promise", "features", "pricing", "faq", "cta"],
                   auth=dict(methods=["email_password", "google"], register_fields=["Name", "Email", "Password"],
                             onboarding=["Name your workspace", "Invite your team", "Take the 2-minute tour"]),
                   web=dict(nav="sidebar", home="dashboard")),
    },
    "mobile_diary": {
        "name": "Mobile-first Diary",
        "summary": "A phone app people share things into from any other app, kept as a dated diary, with a web companion for bigger work.",
        "fits": "Capture, journaling and personal-library apps",
        "bp": dict(platforms="both", primary="mobile",
                   tokens=dict(heading_font="Plus Jakarta Sans", body_font="Inter", radius="soft", density="comfortable"),
                   public_pages=["Landing", "Download app", "About"], landing_sections=["hero", "features", "download", "faq", "cta"],
                   auth=dict(methods=["mobile_otp", "google", "apple"], register_fields=["Name", "Mobile number"],
                             onboarding=["Allow notifications", "Add the app to your Share menu", "Share your first link"]),
                   web=dict(nav="top", home="feed"),
                   mobile=dict(tabs=["Diary", "Search", "Insights", "Profile"], share_target=True, push=True, offline=True)),
    },
    "dashboard": {
        "name": "Dashboard & Admin",
        "summary": "Data-dense web app: KPI tiles, tables, filters and approvals. Minimal public site, sign-in first.",
        "fits": "Internal tools, operations and reporting",
        "bp": dict(platforms="web", primary="web",
                   tokens=dict(heading_font="Inter", body_font="Inter", radius="sharp", density="compact"),
                   public_pages=["Landing"], landing_sections=["hero", "features", "cta"],
                   auth=dict(methods=["email_password", "sso"], register_fields=["Name", "Work email", "Password"],
                             onboarding=["Connect your data source", "Invite colleagues"]),
                   web=dict(nav="sidebar", home="dashboard")),
    },
    "marketplace": {
        "name": "Marketplace & Directory",
        "summary": "Visitors browse and search listings without an account; sign in to save, enquire, book or buy.",
        "fits": "Listings, bookings, catalogues",
        "bp": dict(platforms="both", primary="web",
                   tokens=dict(heading_font="Outfit", body_font="Inter", radius="rounded", density="comfortable"),
                   public_pages=["Landing", "About", "Contact"], landing_sections=["hero", "features", "promise", "faq", "cta"],
                   public_features="Browse and search listings",
                   auth=dict(methods=["email_otp", "google"], register_fields=["Name", "Email"], onboarding=["Pick your interests"]),
                   web=dict(nav="top", home="feed"),
                   mobile=dict(tabs=["Explore", "Saved", "Bookings", "Profile"], push=True)),
    },
    "community": {
        "name": "Content & Community",
        "summary": "A feed of posts, profiles and conversations, built mobile-first with a matching web app.",
        "fits": "Communities, creators, learning",
        "bp": dict(platforms="both", primary="mobile",
                   tokens=dict(heading_font="Poppins", body_font="Nunito Sans", radius="soft", density="comfortable"),
                   public_pages=["Landing", "Download app", "About"], landing_sections=["hero", "features", "download", "cta"],
                   auth=dict(methods=["mobile_otp", "google", "apple"], register_fields=["Name", "Username", "Mobile number"],
                             onboarding=["Choose topics", "Follow a few people", "Set up your profile"]),
                   web=dict(nav="top", home="feed"),
                   mobile=dict(tabs=["Home", "Explore", "Create", "Inbox", "Profile"], push=True)),
    },
    "workflow": {
        "name": "Workflow & Cases",
        "summary": "Work arrives in a queue, is handled on a case page and moves through approvals. Web first, with a phone app for approvers on the go.",
        "fits": "Requests, HR, service desks, compliance",
        "bp": dict(platforms="web", primary="web",
                   tokens=dict(heading_font="Manrope", body_font="Source Sans 3", radius="rounded", density="compact"),
                   public_pages=["Landing", "Pricing"], landing_sections=["hero", "promise", "features", "pricing", "cta"],
                   auth=dict(methods=["email_password", "sso"], register_fields=["Name", "Work email", "Password"],
                             onboarding=["Set up your team", "Choose your approval rules"]),
                   web=dict(nav="sidebar", home="inbox")),
    },
}


def catalogue() -> list[dict]:
    return [{"key": k, "name": t["name"], "summary": t["summary"], "fits": t["fits"],
             "platforms": t["bp"]["platforms"], "primary": t["bp"]["primary"]} for k, t in TEMPLATES.items()]


def suggest(state) -> str:
    """Template that best fits the concept brief (a starting point only)."""
    b = state.concept_brief
    text = " ".join(filter(None, [b.platforms, b.input_channels, b.core_workflow, b.summary] if b else [])) + " " + (state.concept_summary or "")
    t = text.lower()
    if re.search(r"\b(share|diary|journal|capture|save for later|read later)\b", t) and re.search(r"\b(mobile|app|android|ios|phone)\b", t):
        return "mobile_diary"
    if re.search(r"\b(marketplace|listing|booking|directory|catalogue|catalog)\b", t):
        return "marketplace"
    if re.search(r"\b(community|social|feed|followers|creator)\b", t):
        return "community"
    if re.search(r"\b(approval|ticket|case|request|workflow|hr|leave)\b", t):
        return "workflow"
    if re.search(r"\b(dashboard|report|analytics|admin|monitor)\b", t):
        return "dashboard"
    return "saas"


def from_template(key: str, state=None) -> ExperienceBlueprint:
    t = TEMPLATES.get(key)
    if not t:
        raise KeyError(key)
    d = t["bp"]
    bp = ExperienceBlueprint(
        template_key=key, platforms=d["platforms"], primary=d["primary"], tokens=ExperienceTokens(**d["tokens"]),
        public_pages=list(d["public_pages"]), landing_sections=list(d["landing_sections"]),
        public_features=d.get("public_features", ""), auth=AuthSpec(**d["auth"]), web=WebShell(**d["web"]),
        mobile=MobileShell(**d.get("mobile", {})),
    )
    if state is not None:  # carry over what the concept already says about public access
        pub = [m.name for m in state.module_specs if m.access in ("public", "mixed")]
        if pub and not bp.public_features:
            bp.public_features = ", ".join(pub)
    return normalise(bp)


def normalise(bp: ExperienceBlueprint) -> ExperienceBlueprint:
    """Clamp an edited blueprint to values the renderer understands."""
    bp = bp.model_copy(deep=True)
    bp.platforms = bp.platforms if bp.platforms in PLATFORMS else "web"
    bp.primary = "web" if bp.platforms == "web" else "mobile" if bp.platforms == "mobile" else (bp.primary if bp.primary in ("web", "mobile") else "web")
    tk = bp.tokens
    tk.heading_font = tk.heading_font if tk.heading_font in FONTS else "Space Grotesk"
    tk.body_font = tk.body_font if tk.body_font in FONTS else "IBM Plex Sans"
    tk.radius = tk.radius if tk.radius in RADII else "rounded"
    tk.density = tk.density if tk.density in DENSITIES else "comfortable"
    secs = [s for s in dict.fromkeys(bp.landing_sections) if s in SECTIONS]
    if bp.platforms == "web":
        secs = [s for s in secs if s != "download"]
    bp.landing_sections = (["hero"] if "hero" not in secs else []) + secs
    pages = [p for p in dict.fromkeys(bp.public_pages) if p in PAGES]
    if bp.platforms == "web":
        pages = [p for p in pages if p != "Download app"]
    bp.public_pages = (["Landing"] if "Landing" not in pages else []) + pages
    bp.auth.methods = [m for m in dict.fromkeys(bp.auth.methods) if m in AUTH_METHODS] or ["email_password"]
    bp.auth.register_fields = [f.strip()[:40] for f in bp.auth.register_fields if f.strip()][:6] or ["Name", "Email"]
    bp.auth.onboarding = [f.strip()[:60] for f in bp.auth.onboarding if f.strip()][:5]
    bp.web.nav = bp.web.nav if bp.web.nav in NAVS else "sidebar"
    bp.web.home = bp.web.home if bp.web.home in HOMES else "dashboard"
    if bp.platforms == "web":
        bp.mobile = MobileShell()
    else:
        bp.mobile.tabs = [t.strip()[:18] for t in bp.mobile.tabs if t.strip()][:5] or ["Home", "Search", "Profile"]
    bp.public_features = bp.public_features.strip()[:300]
    bp.notes = bp.notes.strip()[:600]
    return bp


def freeze(bp: ExperienceBlueprint, previous: str = "") -> ExperienceBlueprint:
    bp = bp.model_copy(deep=True)
    if previous:
        major, _, minor = previous.partition(".")
        bp.version = f"{major}.{int(minor or 0) + 1}"
    else:
        bp.version = "1.0"
    bp.frozen = True
    bp.frozen_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return bp


def summary_text(bp: ExperienceBlueprint) -> str:
    """Plain-language blueprint for AI prompts and documents."""
    if not bp:
        return ""
    plat = {"web": "a web portal", "mobile": "a mobile app", "both": f"a mobile app and a web portal ({bp.primary} first)"}[bp.platforms]
    lines = [
        f"Product is {plat}; template: {TEMPLATES.get(bp.template_key, {}).get('name', 'custom')}.",
        f"Public pages: {', '.join(bp.public_pages)}; landing sections in order: {', '.join(bp.landing_sections)}.",
        f"Visitors may use without signing in: {bp.public_features or 'nothing beyond the public pages'}.",
        f"Sign-in: {', '.join(AUTH_METHODS[m] for m in bp.auth.methods)}; register fields: {', '.join(bp.auth.register_fields)}"
        + (f"; first-run onboarding: {', '.join(bp.auth.onboarding)}." if bp.auth.onboarding else "."),
    ]
    if bp.platforms != "mobile":
        lines.append(f"Web app: {bp.web.nav} navigation, home screen is a {bp.web.home}.")
    if bp.platforms != "web":
        lines.append(f"Mobile app: bottom tabs {', '.join(bp.mobile.tabs)}"
                     + ("; appears in the phone's Share menu" if bp.mobile.share_target else "")
                     + ("; works offline and syncs later" if bp.mobile.offline else "")
                     + ("; push notifications" if bp.mobile.push else "") + ".")
    if bp.module_slots:
        lines.append("Module placement: " + "; ".join(f"{m} -> {s}" for m, s in bp.module_slots.items()) + ".")
    return " ".join(lines)


# --------------------------------------------------------------------------
# Clickable skeleton preview
# --------------------------------------------------------------------------
def _home_blocks(home: str, name: str) -> list[UIBlock]:
    if home == "feed":
        return [UIBlock(type="tabs", items=["For you", "Recent", "Saved"]),
                UIBlock(type="cards", items=["Item from your modules — appears here once screens are designed",
                                             "Another item — newest first", "Pinned item — kept at the top"]),
                UIBlock(type="buttons", actions=["Open item", "Filter"])]
    if home == "inbox":
        return [UIBlock(type="stats", items=["Waiting for you: 12", "Due today: 3", "Done this week: 41"]),
                UIBlock(type="list", title="Your queue", items=["New request — Today", "Needs approval — Yesterday", "Waiting on others — 2 days"]),
                UIBlock(type="buttons", actions=["Open next", "View all"])]
    return [UIBlock(type="stats", items=["Key figure: 1,284", "This week: +12%", "Open items: 7", "Health: OK"]),
            UIBlock(type="table", title="Recent activity", columns=["Item", "Owner", "Status"],
                    rows=[["First record", "You", "Active"], ["Second record", "Team", "Review"], ["Third record", "You", "Done"]]),
            UIBlock(type="notice", title="Your modules plug in here.", text=f"After Freeze Scope each {name} module gets a place in this frame.")]


def preview_modules(state, bp: ExperienceBlueprint) -> tuple[list[UIModule], list[str]]:
    """UI modules for the skeleton prototype, plus the web navigation items."""
    from . import site_kit
    name = state.selected_name or "Product"
    mods: list[UIModule] = []

    def mod(i, title, screens):
        mods.append(UIModule(ui_id=f"BP-{i:02d}", module=title, req_id="", title=title, doc=UIDoc(screens=screens)))

    public = site_kit.apply(state, UIDoc(screens=[]), bp=bp, home="Home").screens
    mod(1, "Sign-in & Account", public)

    slots = [m.name for m in state.module_specs if m.kind != "standard"] or ["Module one", "Module two", "Module three"]
    nav = ["Home"] + slots[:5] + ["Settings"]
    first = "Home"
    screens = []
    if bp.platforms != "mobile":
        screens.append(UIScreen(screen_id="H1", name="Home", purpose=f"Where a signed-in user lands on the web ({bp.web.home}).",
                                route="/app", layout="app", blocks=_home_blocks(bp.web.home, name)))
    if bp.platforms != "web":
        tab0 = bp.mobile.tabs[0] if bp.mobile.tabs else "Home"
        screens.append(UIScreen(screen_id="M1", name=f"{tab0} (app)", purpose="The first tab of the phone app.", route="app://home", layout="mobile",
                                blocks=[UIBlock(type="tabs", items=["Today", "This week", "All"]),
                                        UIBlock(type="cards", items=["Shared from another app — 2 min ago", "Saved link — processed and summarised",
                                                                     "Voice note — transcribed"]),
                                        UIBlock(type="buttons", actions=["Open", "Add"])]))
        if bp.mobile.share_target:
            screens.append(UIScreen(screen_id="M2", name=f"Share to {name}", purpose="The phone's Share menu: save in one tap, processing happens later on the server.",
                                    route="share://", layout="mobile",
                                    blocks=[UIBlock(type="notice", title="Shared from another app.", text="https://example.com/a-link-you-shared"),
                                            UIBlock(type="form", items=["Add a note (optional)", "Tag"], actions=[f"Save to {name}", "Cancel"]),
                                            UIBlock(type="text", text="Saved instantly. Summary and analysis arrive in a moment.")]))
    mod(2, first, screens)
    for i, sname in enumerate(slots[:5], 3):
        lay = "mobile" if bp.primary == "mobile" else "app"
        mod(i, sname, [UIScreen(screen_id="X1", name=sname, purpose="Placeholder: this module's screens are designed in the UI/UX stage.",
                                route=f"/{re.sub(r'[^a-z0-9]+', '-', sname.lower()).strip('-')}", layout=lay,
                                blocks=[UIBlock(type="notice", title="Module area.", text=f"{sname} is drawn here, inside this frame, in the UI/UX stage."),
                                        UIBlock(type="media", title="Module content")])])
    mod(9, "Settings", [UIScreen(screen_id="S1", name="Settings", purpose="Standard settings every product ships with.", route="/settings",
                                 layout="mobile" if bp.primary == "mobile" else "app",
                                 blocks=[UIBlock(type="list", items=["Profile — name, photo", "Notifications — email, push", "Connected accounts — social, storage",
                                                                     "Privacy & data — download or delete", "Sign out"])])])
    return mods, nav
