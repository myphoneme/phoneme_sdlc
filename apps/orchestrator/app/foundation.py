"""
GiveWings Standard Modules ("the chassis").

2026-10-01 product decision (Anuj): GiveWings is a factory -- every product
it produces is independent and self-contained, ships with its own code and
can be hosted anywhere. Sign-in, profile & settings, admin & roles, and
security/audit/health are therefore NOT borrowed from a shared platform;
they are standard modules included in every product, written from a
versioned GiveWings master template and tailored to the product (sign-in
method, roles, market). Each product also carries a health agent that
reports to its own admin console and, when the owner connects it, to the
GiveWings Health Dashboard.

Only product-specific business modules go through AI breakdown and Flow
Design; standard modules arrive with a pre-approved standard flow.
"""
import json
import logging
import re

from . import ai_router, reqdoc
from .models import AcceptanceCriterion, JourneyStep, ModuleSpec, RequirementDoc

logger = logging.getLogger("phoneme.foundation")

STANDARD_VERSION = "1.0"


def _j(actor, title, detail):
    return {"actor": actor, "title": title, "detail": detail}


def _ac(criterion, priority="Must"):
    return {"criterion": criterion, "priority": priority}


CATALOG: list[dict] = [
    {
        "key": "account",
        "name": "Sign-in & Account",
        "position": "first",
        "description": "Lets people create an account, sign in and out, and recover access, while keeping public pages open to visitors.",
        "tailoring_hint": "e.g. Sign in with mobile OTP over WhatsApp; Google sign-in as an option; no passwords",
        "doc": {
            "summary": "Lets visitors become registered users and lets registered users sign in, stay signed in safely and sign out. Public pages such as the landing page, trial tools or contests stay open to visitors; everything that holds a user's own data needs sign-in.",
            "actors": ["Visitor", "User", "{product} (system)"],
            "journey": [
                _j("Visitor", "Explores public pages", "A visitor can use the landing page and any features marked public without an account."),
                _j("Visitor", "Creates an account", "The visitor signs up with the product's chosen sign-in method and accepts the terms and privacy notice."),
                _j("{product} (system)", "Verifies identity", "The product confirms the email address or mobile number with a one-time code before the account is active."),
                _j("User", "Signs in", "The user signs in and lands on their home screen; a remembered device keeps them signed in for an agreed period."),
                _j("User", "Recovers access", "A user who forgets their sign-in details resets them with a one-time code sent to their verified contact."),
                _j("User", "Signs out", "The user signs out from the current device or from all devices at once."),
            ],
            "business_rules": [
                "Features that hold or change a user's own data are available only to signed-in users; public features are listed explicitly in each module's access setting.",
                "A user may hold only one account per verified email address or mobile number.",
                "Repeated failed sign-in attempts temporarily lock the account and notify the owner.",
                "Signed-in sessions end automatically after a period of inactivity agreed for this product.",
                "Users must accept the current terms and privacy notice before their account is active.",
            ],
            "acceptance_criteria": [
                _ac("Given a visitor, when they open a public page or public feature, then it works without asking them to sign in."),
                _ac("Given a visitor, when they open a feature that needs an account, then they are asked to sign up or sign in and return to the same place afterwards."),
                _ac("Given a new sign-up, when the one-time code is confirmed, then the account becomes active and the user is signed in."),
                _ac("Given five failed sign-in attempts in a row, when another attempt is made, then the account is temporarily locked and the owner is notified."),
                _ac("Given a signed-in user, when they choose sign out from all devices, then every active session ends."),
                _ac("Given a user who forgot their sign-in details, when they complete recovery with a one-time code, then they can sign in again.", "Must"),
                _ac("Given a returning user on a remembered device, when they open the product within the agreed period, then they are still signed in.", "Should"),
            ],
            "out_of_scope": ["Single sign-on with a customer's corporate directory (added per product when required)."],
        },
    },
    {
        "key": "profile",
        "name": "Profile & Settings",
        "position": "after",
        "description": "Lets each user manage their profile, preferences, notifications and personal data.",
        "tailoring_hint": "e.g. Profile holds brand voice and preferred content formats; Hindi and English",
        "doc": {
            "summary": "Gives every signed-in user one place to manage who they are in the product and how it behaves for them: profile details, preferences, notifications, connected accounts and their personal data.",
            "actors": ["User", "{product} (system)"],
            "journey": [
                _j("{product} (system)", "Creates a starter profile", "When an account becomes active, the product creates a profile with sensible defaults."),
                _j("User", "Completes the profile", "The user adds their details and the product-specific preferences that personalise their experience."),
                _j("User", "Sets notifications", "The user chooses which messages they receive and on which channel."),
                _j("User", "Manages connected accounts", "The user links or unlinks outside accounts the product uses on their behalf."),
                _j("User", "Downloads or deletes their data", "The user downloads a copy of their data or asks for their account and data to be deleted."),
            ],
            "business_rules": [
                "Only the user (and authorised admins, as recorded in the audit log) can view or change a user's profile.",
                "Changing a verified email address or mobile number requires confirming the new one with a one-time code.",
                "A deletion request removes the user's personal data within the period stated in the privacy notice, except records the law requires to be kept.",
                "Preferences take effect immediately across every device the user is signed in on.",
            ],
            "acceptance_criteria": [
                _ac("Given a new account, when it becomes active, then a profile with default preferences exists."),
                _ac("Given a user, when they change a preference, then the change takes effect immediately on all their devices."),
                _ac("Given a user, when they change their verified email or mobile, then the change applies only after the new contact is confirmed."),
                _ac("Given a user, when they turn a notification type off, then they stop receiving it on that channel."),
                _ac("Given a user, when they request a copy of their data, then they receive a complete, readable export."),
                _ac("Given a user, when they request account deletion and confirm it, then their account is closed and their personal data is removed within the stated period."),
            ],
            "out_of_scope": [],
        },
    },
    {
        "key": "admin",
        "name": "Admin Dashboard & Roles",
        "position": "after",
        "description": "Gives the product's operators a console to manage users, roles and permissions, configuration and usage.",
        "tailoring_hint": "e.g. Roles: Owner, Editor, Viewer; admins approve public campaigns",
        "doc": {
            "summary": "Gives the people who run the product a single console to manage users, decide who may do what through roles, adjust product configuration and see how the product is being used.",
            "actors": ["Owner", "Admin", "User", "{product} (system)"],
            "journey": [
                _j("Owner", "Sets up the first admin", "The product owner becomes the first admin when the product is installed."),
                _j("Admin", "Reviews users", "An admin searches, views, suspends or reinstates user accounts."),
                _j("Admin", "Assigns roles", "An admin gives users roles that decide which features and data they can use."),
                _j("Admin", "Adjusts configuration", "An admin changes product settings such as limits, public features and messages without a new release."),
                _j("Admin", "Watches usage", "An admin sees active users, sign-ups and use of each module over a chosen period."),
            ],
            "business_rules": [
                "Every product has at least one Owner; the last Owner cannot be removed or demoted.",
                "Users can only reach features and data allowed by their role; new users get the least-privileged role by default.",
                "Every admin action is recorded in the audit log with who did it and when.",
                "Configuration changes take effect without a new release and can be rolled back to the previous value.",
            ],
            "acceptance_criteria": [
                _ac("Given a user without the required role, when they try to open an admin or restricted feature, then access is refused."),
                _ac("Given an admin, when they suspend a user, then that user is signed out and cannot sign in until reinstated."),
                _ac("Given an admin, when they change a user's role, then the user's access changes on their next action."),
                _ac("Given the last Owner, when anyone tries to remove or demote them, then the change is refused."),
                _ac("Given an admin, when they change a configuration value, then it applies immediately and the previous value can be restored."),
                _ac("Given an admin, when they open the usage view, then they see active users and use of each module for the chosen period.", "Should"),
            ],
            "out_of_scope": ["Billing and subscriptions (a separate module when the product charges users)."],
        },
    },
    {
        "key": "ops",
        "name": "Security, Audit & Health",
        "position": "last",
        "description": "Protects data, keeps an audit trail, backs up, and runs a health agent that monitors every module and reports to the GiveWings Health Dashboard.",
        "tailoring_hint": "e.g. Data stays in India; alert the owner on WhatsApp; keep audit records for 3 years",
        "doc": {
            "summary": "Keeps the product and its users' data safe and the service dependable: data protection, an audit trail of important actions, backups, and a built-in health agent that watches every module, alerts the operators and reports the product's health to the GiveWings Health Dashboard.",
            "actors": ["Owner", "Admin", "{product} (system)", "{product} Health Agent", "GiveWings Health Dashboard"],
            "journey": [
                _j("{product} (system)", "Protects data", "All personal and business data is protected in storage and in transit, and only reachable through the product's own permissions."),
                _j("{product} (system)", "Records the audit trail", "Sign-ins, permission changes, admin actions and data exports are recorded and cannot be altered."),
                _j("{product} Health Agent", "Checks each module", "The health agent regularly checks that every module is up and responding within agreed limits."),
                _j("{product} Health Agent", "Reports health", "The agent reports each module's status, response times and error rates to the admin console and, once the owner connects it, to the GiveWings Health Dashboard."),
                _j("{product} Health Agent", "Raises alerts", "When a module fails or slows beyond its limit, the agent alerts the owner and admins on their chosen channel."),
                _j("{product} (system)", "Backs up and restores", "Data is backed up on a schedule, and a restore is tested regularly."),
            ],
            "business_rules": [
                "Every module of the product is covered by the health agent from its first release.",
                "Health reports sent to the GiveWings Health Dashboard contain only service health information, never users' personal or business data.",
                "The product works fully even when the GiveWings Health Dashboard is not connected or unreachable.",
                "Audit records cannot be edited or deleted by anyone, including admins, for the retention period agreed for this product.",
                "Data is stored in the region required by the product's market and regulations.",
                "Backups are kept for an agreed period and a restore is tested at least every quarter.",
            ],
            "acceptance_criteria": [
                _ac("Given a running product, when the admin opens the health view, then they see the current status of every module."),
                _ac("Given a module that stops responding, when the health agent detects it, then the owner and admins are alerted within the agreed time."),
                _ac("Given the owner has connected the product to GiveWings, when the health agent reports, then the GiveWings Health Dashboard shows the product's module health without any personal data."),
                _ac("Given the GiveWings Health Dashboard is unreachable, when users use the product, then every feature keeps working."),
                _ac("Given an admin changes a user's role, when the audit log is opened, then the change is listed with who made it and when, and cannot be edited."),
                _ac("Given a scheduled backup, when a test restore is run, then the product's data is recovered completely."),
            ],
            "out_of_scope": ["Formal security certification (planned per product when its market requires it)."],
        },
    },
]

BY_KEY = {c["key"]: c for c in CATALOG}
NAMES = {c["name"].lower(): c["key"] for c in CATALOG}

# Legacy 'Platform-Core' modules and AI suggestions covering these concerns
# are replaced by the standard modules. Word-boundary phrases only, so
# business modules such as "Accounts Payable" or "Course Administration"
# are never swallowed.
_COVERED = re.compile(
    r"\b(auth(entication|orisation|orization)?|sign[- ]?in|sign[- ]?up|log[- ]?in|log[- ]?out|"
    r"user accounts?|account management|identity( management)?|access control|"
    r"roles?( (and|&) permissions?)?|permissions?|admin (dashboard|console|panel)|"
    r"user profiles?|profile (and|&) settings|user settings|security|audit( logs?| trail)?|"
    r"health( monitoring| checks?)?|monitoring|observability|api gateway|backups?)\b",
    re.I,
)


def covers(name: str, description: str = "") -> bool:
    """True when a proposed module is really one of the standard concerns."""
    n = re.sub(r"^platform-core:\s*", "", name.strip(), flags=re.I)
    if n.lower() in NAMES:
        return True
    return bool(_COVERED.search(n))


def standard_spec(key: str, tailoring: str = "") -> ModuleSpec:
    c = BY_KEY[key]
    return ModuleSpec(
        name=c["name"], description=c["description"], kind="standard",
        standard_key=key, tailoring=tailoring, access="signed_in",
    )


def ensure(specs: list[ModuleSpec]) -> list[ModuleSpec]:
    """Normalise a module list: drop anything the standard modules cover
    that was marked Platform-Core (legacy), turn remaining legacy
    Platform-Core modules into product modules, make sure every standard
    module is present once, and order: Sign-in first, product modules,
    then the remaining standard modules."""
    tailoring = {m.standard_key: m.tailoring for m in specs if m.kind == "standard" and m.standard_key}
    business: list[ModuleSpec] = []
    for m in specs:
        if m.kind == "standard":
            continue
        if m.name.strip().lower() in NAMES:
            continue
        if m.platform_core and covers(m.name):
            continue
        business.append(m.model_copy(update={"platform_core": False, "kind": "business", "standard_key": ""}))
    first = [standard_spec(c["key"], tailoring.get(c["key"], "")) for c in CATALOG if c["position"] == "first"]
    rest = [standard_spec(c["key"], tailoring.get(c["key"], "")) for c in CATALOG if c["position"] != "first"]
    return first + business + rest


def module_names(specs: list[ModuleSpec]) -> list[str]:
    return [m.name for m in specs]


def key_for(specs: list[ModuleSpec], module: str) -> str:
    for m in specs:
        if m.name == module and m.kind == "standard":
            return m.standard_key
    return ""


def _fill(text: str, product: str) -> str:
    return text.replace("{product}", product)


def template_doc(key: str, product: str) -> RequirementDoc:
    d = BY_KEY[key]["doc"]
    return RequirementDoc(
        summary=_fill(d["summary"], product),
        actors=[_fill(a, product) for a in d["actors"]],
        journey=[JourneyStep(**{k: _fill(v, product) for k, v in s.items()}) for s in d["journey"]],
        business_rules=[_fill(r, product) for r in d["business_rules"]],
        acceptance_criteria=[
            AcceptanceCriterion(id=f"AC{i}", criterion=_fill(a["criterion"], product), priority=a["priority"])
            for i, a in enumerate(d["acceptance_criteria"], start=1)
        ],
        out_of_scope=[_fill(x, product) for x in d["out_of_scope"]],
    )


def flow_steps(key: str, product: str) -> list[str]:
    return [f"{_fill(s['actor'], product)}: {_fill(s['title'], product)} — {_fill(s['detail'], product)}" for s in BY_KEY[key]["doc"]["journey"]]


async def tailored_doc(key: str, product: str, concept: str, tailoring: str, public_features: str, module_map: str) -> tuple[str, RequirementDoc]:
    """Standard template + product tailoring. The AI may adapt wording and
    add product-specific rules/criteria but must keep every standard
    acceptance criterion; if it drops any, or fails, the template is used
    as-is so the standard is never weakened."""
    c = BY_KEY[key]
    base = template_doc(key, product)
    if not (tailoring.strip() or concept.strip()):
        return c["name"], base
    prompt = (
        f"Product: {product}\nConcept: {concept}\n"
        f"All modules of this product:\n{module_map}\n\n"
        f"Module: {c['name']} -- a GiveWings STANDARD module (template v{STANDARD_VERSION}).\n"
        f"Product-specific tailoring from the business analyst: {tailoring or 'none'}\n"
        + (f"Features this product makes public (no sign-in): {public_features}\n" if public_features and key == "account" else "")
        + "\nHere is the standard requirement. Tailor it to this product: adapt wording, "
        "name the product's sign-in method / roles / channels where the tailoring says so, and "
        "ADD product-specific business rules or acceptance criteria if the tailoring needs them. "
        "You MUST keep every standard journey step, business rule and acceptance criterion "
        "(you may reword them to fit, never remove or weaken them). Keep the title exactly "
        f"'{c['name']}'.\n\n"
        + json.dumps({"title": c["name"], **base.model_dump()}, ensure_ascii=False)
    )
    try:
        title, doc = await reqdoc.generate_doc(prompt, fallback_title=c["name"])
    except Exception:  # noqa: BLE001 -- never block drafting on tailoring
        logger.exception("Tailoring failed for standard module %s -- using template", key)
        return c["name"], base
    if len(doc.acceptance_criteria) < len(base.acceptance_criteria) or len(doc.business_rules) < len(base.business_rules):
        logger.warning("Tailored %s dropped standard items -- using template", key)
        return c["name"], base
    return c["name"], doc
