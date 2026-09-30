"""
Structured BRD/PRD requirement documents.

2026-09-30 review of the RelayReel dry run: requirements came out as dense
paragraphs mixing business intent with API paths (POST /ingestion/intake),
table/queue names (vault_raw_messages, ingestion_parse_queue) and status
codes. That is (a) hard for stakeholders to read and (b) premature -- the
technical mapping belongs in the Technical Design stage, which is produced
*from* the frozen BRD/PRD, not inside it.

Every requirement is now a RequirementDoc: summary, actors, a numbered
"how it works" journey (short heading + one-line detail + who does it),
business rules, a Given/When/Then acceptance-criteria matrix with
priorities, out-of-scope and open questions -- all in business language.
A lint pass catches technical leakage and triggers one plain-language
rewrite before anything is saved.
"""
import json
import logging
import re

from . import ai_router
from .models import AcceptanceCriterion, JourneyStep, RequirementDoc

logger = logging.getLogger("phoneme.reqdoc")

BUSINESS_LANGUAGE_RULES = (
    "Write for business stakeholders, the way a senior business analyst "
    "writes a BRD/PRD. Plain, short sentences. NEVER include API endpoints, "
    "URLs or paths, HTTP methods (GET/POST/...), HTTP status codes, database "
    "table or column names, queue or event names, field names, "
    "snake_case/camelCase identifiers, JSON, code, or technology/vendor "
    "choices for the implementation. Say what happens and who does it "
    "(e.g. 'The system saves the forwarded link to the user's private "
    "vault'), not how it is built -- the technical mapping is produced "
    "later in the Technical Design stage."
)

DOC_SCHEMA = """Respond with ONLY one JSON object (no markdown fences):
{
  "title": "<requirement title, max 8 words, plain language>",
  "summary": "<2-3 sentences: what this module lets people do and why it matters>",
  "actors": ["<who is involved, e.g. 'Content creator', 'RelayReel (system)', 'GiveWings AI'>"],
  "journey": [
    {"title": "<step heading, 2-6 words>", "detail": "<one plain sentence describing what happens>", "actor": "<one of the actors>"}
  ],
  "business_rules": ["<a rule the product must always follow, one sentence>"],
  "acceptance_criteria": [
    {"criterion": "<testable, plain language: Given ..., when ..., then ...>", "priority": "Must|Should|Could"}
  ],
  "out_of_scope": ["<explicitly not part of this module>"],
  "open_questions": ["<decision still needed from the business, if any>"]
}
journey: 4-8 steps in the order they happen. acceptance_criteria: 4-8
items, each independently testable. Keep every list item to one sentence.
Use empty lists where nothing applies -- never pad."""

_TECH_PATTERNS = [
    (re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+/", re.I), "HTTP method + path"),
    (re.compile(r"(?<![\w.])/[A-Za-z0-9_{}:\-]+(?:/[A-Za-z0-9_{}:\-]+)+"), "URL path"),
    (re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b"), "snake_case identifier"),
    (re.compile(r"\b[a-z]{2,}[A-Z][a-z]{2,}\w*\b"), "camelCase identifier"),
    (re.compile(r"\b(?:returns?|returning|respond(?:s|ing)? with)\s+[1-5]\d\d\b", re.I), "status code"),
]


def technical_leaks(text: str) -> list[str]:
    found = []
    for rx, label in _TECH_PATTERNS:
        m = rx.search(text)
        if m:
            found.append(f"{label}: '{m.group(0)}'")
    return found


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"```\s*$", "", text)
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b < a:
        raise ValueError("no JSON object in response")
    return json.loads(text[a:b + 1])


def _clean(s) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", s)
    return s.strip(" -•")


def _strs(v) -> list[str]:
    return [_clean(x) for x in (v or []) if _clean(x)]


def parse_doc(data: dict) -> tuple[str, RequirementDoc]:
    journey = [
        JourneyStep(title=_clean(j.get("title")), detail=_clean(j.get("detail")), actor=_clean(j.get("actor")))
        for j in (data.get("journey") or []) if isinstance(j, dict) and _clean(j.get("title"))
    ]
    acs = []
    for a in (data.get("acceptance_criteria") or []):
        crit = _clean(a.get("criterion")) if isinstance(a, dict) else ""
        if not crit:
            continue
        pr = _clean(a.get("priority")).capitalize()
        acs.append(AcceptanceCriterion(id=f"AC{len(acs) + 1}", criterion=crit, priority=pr if pr in ("Must", "Should", "Could") else "Must"))
    doc = RequirementDoc(
        summary=_clean(data.get("summary")),
        actors=_strs(data.get("actors")),
        journey=journey,
        business_rules=_strs(data.get("business_rules")),
        acceptance_criteria=acs,
        out_of_scope=_strs(data.get("out_of_scope")),
        open_questions=_strs(data.get("open_questions")),
    )
    return _clean(data.get("title")), doc


def render_text(title: str, doc: RequirementDoc) -> str:
    """Plain-text rendering -- stored as `body` so AI rewrites, exports and
    any legacy reader still get the whole requirement."""
    out = [title, "", doc.summary]
    if doc.actors:
        out += ["", "Who is involved: " + ", ".join(doc.actors)]
    if doc.journey:
        out += ["", "How it works:"]
        out += [f"{i}. {s.title}{f' ({s.actor})' if s.actor else ''} — {s.detail}" for i, s in enumerate(doc.journey, 1)]
    if doc.business_rules:
        out += ["", "Business rules:"] + [f"- {r}" for r in doc.business_rules]
    if doc.acceptance_criteria:
        out += ["", "Acceptance criteria:"] + [f"{a.id} [{a.priority}] {a.criterion}" for a in doc.acceptance_criteria]
    if doc.out_of_scope:
        out += ["", "Out of scope:"] + [f"- {x}" for x in doc.out_of_scope]
    if doc.open_questions:
        out += ["", "Open questions:"] + [f"- {x}" for x in doc.open_questions]
    return "\n".join(out).strip()


async def generate_doc(prompt: str, fallback_title: str) -> tuple[str, RequirementDoc]:
    """Draft (or rewrite) a structured requirement; if the draft leaks
    implementation detail, ask once more for a business-language rewrite."""
    system = "You are the BRD/PRD step of the Idea-to-BRD/PRD Wizard. " + BUSINESS_LANGUAGE_RULES + " JSON only."
    result = await ai_router.generate(ai_router.Feature.BRD_PRD_DRAFTING, f"{prompt}\n\n{DOC_SCHEMA}", system=system)
    title, doc = parse_doc(_extract_json(result["text"]))
    leaks = technical_leaks(render_text(title, doc))
    if leaks:
        logger.info("Requirement draft leaked implementation detail (%s) -- rewriting", "; ".join(leaks[:3]))
        fix = await ai_router.generate(
            ai_router.Feature.BRD_PRD_DRAFTING,
            "This BRD/PRD requirement contains implementation detail that "
            f"does not belong in a business document ({'; '.join(leaks[:5])}). "
            "Rewrite it in business language with the same meaning and "
            "structure, removing every endpoint, path, table/queue/field "
            f"name, identifier and status code.\n\n{json.dumps({'title': title, **doc.model_dump()}, ensure_ascii=False)}\n\n{DOC_SCHEMA}",
            system=system,
        )
        try:
            title, doc = parse_doc(_extract_json(fix["text"]))
        except (ValueError, json.JSONDecodeError):
            logger.warning("Business-language rewrite failed to parse; keeping first draft")
    return title or fallback_title, doc
