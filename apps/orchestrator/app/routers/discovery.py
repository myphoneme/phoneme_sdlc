"""
Stage 1 (Discovery Chat) and Stage 2 (User Flow / Identity) endpoints.

Ports the onboarding-wizard-mock.html flow onto real backend calls, routed
through ai_router per the frozen model policy: discovery-chat NLU and the
custom-name check are non-critical (Ollama); competitive-research
summarization and the eventual module breakdown are critical (commercial).
"""
import json
import logging
import re

from fastapi import APIRouter, HTTPException

from .. import ai_router, store
from ..models import (
    StartSessionRequest, ChatTurnRequest, ResearchMoreRequest,
    NameCheckRequest, SelectNameRequest, SelectThemeRequest, SessionState,
    ChatMessage, MarketLandscapeRow, ResearchReport,
)

logger = logging.getLogger("phoneme.discovery")

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

# Discovery chat is force-terminated after this many user turns rather than
# trusting the model to volunteer a 'CONCEPT SUMMARY:' on its own — verified
# against the real AI server (2026-09-25) that it will otherwise keep asking
# open-ended clarifying questions indefinitely (headers, numbered lists,
# multi-part probes) instead of converging. One user turn from /start plus
# this many more /chat turns, then the next /chat call is forced to summarize.
MAX_CLARIFYING_TURNS = 1

CHAT_STYLE_RULE = (
    "Reply in plain conversational prose only — 2-4 sentences, no markdown "
    "headers, no bullet or numbered lists, no emoji. This renders as a single "
    "chat bubble, not a document."
)

def _clean_line(line: str) -> str:
    """Strip bullet markers and markdown emphasis the model adds despite
    being asked for plain text — verified needed against the real AI server,
    which wraps company names in **bold** even when told not to."""
    line = line.strip()
    line = re.sub(r"^(?:[-•]|\*(?!\*))\s*", "", line)  # leading bullet: -, •, or single *
    line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)             # **bold**
    line = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", line)   # *italic*
    return line.strip()


# The framing the user always has in mind for this step but never had to
# type -- carried in the prompt itself now instead of assuming the model
# infers it from a bare concept summary (BRD/PRD Section 18.8 amendment,
# 2026-09-26).
RESEARCH_FRAMING = (
    "I am having a new idea so I want to research over the web: are there "
    "applications already doing that, do proper research for their "
    "features and limitations, and suggest if it is a viable product for "
    "revenue generation and what all features should be incorporated into "
    "it?"
)

RESEARCH_JSON_INSTRUCTIONS = """
Respond with ONLY a single JSON object (no markdown code fences, no prose
before or after it) matching exactly this shape:

{
  "market_landscape": [
    {"category": "<tool category, e.g. 'AI Content Repurposing'>",
     "examples": "<2-4 real, currently operating product names>",
     "what_they_do": "<1-2 sentences>",
     "limitations": "<1-2 sentences on gaps relative to this idea>"}
  ],
  "viability_verdict": "<2-4 sentences: is this viable for revenue generation, and for whom>",
  "market_demand": ["<bullet: evidence of real demand, pricing comparables, or user pain points>"],
  "risks": ["<bullet: a real technical, legal, or platform constraint that would shape the build>"],
  "recommended_features": ["<bullet: a specific feature to incorporate, phrased as a capability, ideally grouped by build phase e.g. 'Phase 1 (Ingestion): ...'>"],
  "monetization": ["<bullet: a concrete pricing tier or revenue lever, e.g. 'Free: X — Pro ($Y/mo): Z'>"],
  "suggested_names": ["<3 short, brandable product name candidates specific to this concept>"]
}

Requirements:
- market_landscape must have 3-6 rows covering distinct tool categories that
  actually compete with or adjoin this idea -- use web search to find REAL
  products, not invented ones. If you cannot verify a product exists, omit it.
- Every list should be specific to THIS product concept, not generic SaaS
  advice that would apply to any idea.
- recommended_features should total 6-12 items across phases.
- suggested_names must be plausible brand names for THIS concept -- never
  reuse a competitor's name.
- Output valid JSON only. Do not wrap it in ```json fences.
"""


def _extract_json_object(text: str) -> dict:
    """Pull a JSON object out of a model response that may still wrap it in
    ```json fences or add stray prose despite instructions not to -- same
    defensive-parsing need as _clean_line, one layer up."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in response: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def _parse_research_report(raw_text: str) -> tuple[ResearchReport, list[str]]:
    data = _extract_json_object(raw_text)
    rows = [
        MarketLandscapeRow(
            category=_clean_line(str(r.get("category", ""))),
            examples=_clean_line(str(r.get("examples", ""))),
            what_they_do=_clean_line(str(r.get("what_they_do", ""))),
            limitations=_clean_line(str(r.get("limitations", ""))),
        )
        for r in data.get("market_landscape", []) if isinstance(r, dict)
    ]
    return ResearchReport(
        market_landscape=rows,
        viability_verdict=_clean_line(str(data.get("viability_verdict", ""))),
        market_demand=[_clean_line(str(x)) for x in data.get("market_demand", [])],
        risks=[_clean_line(str(x)) for x in data.get("risks", [])],
        recommended_features=[_clean_line(str(x)) for x in data.get("recommended_features", [])],
        monetization=[_clean_line(str(x)) for x in data.get("monetization", [])],
    ), [_clean_line(str(x)) for x in data.get("suggested_names", [])]


@router.post("/start", response_model=SessionState)
async def start_session(req: StartSessionRequest):
    state = store.new_session()
    state.messages.append(ChatMessage(role="user", text=req.initial_message))

    result = await ai_router.generate(
        ai_router.Feature.DISCOVERY_CHAT_NLU,
        req.initial_message,
        system=(
            "You are the Phoneme SDLC Platform's Discovery Chat assistant. "
            "The user is describing a new product idea. Reflect back your "
            "understanding of the target users, the core workflow, and the "
            "problem it solves, then ask exactly ONE focused follow-up "
            "question to clarify scope. " + CHAT_STYLE_RULE
        ),
    )
    state.messages.append(ChatMessage(role="assistant", text=result["text"]))
    store.save_session(state)
    return state


@router.post("/chat", response_model=SessionState)
async def chat_turn(req: ChatTurnRequest):
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")

    user_turns_so_far = sum(1 for m in state.messages if m.role == "user")
    state.messages.append(ChatMessage(role="user", text=req.message))
    history = "\n".join(f"{m.role}: {m.text}" for m in state.messages)

    if user_turns_so_far >= MAX_CLARIFYING_TURNS:
        system = (
            "Enough has been shared to scope this product. Do NOT ask any "
            "further questions. Respond with ONLY one paragraph, prefixed "
            "exactly with 'CONCEPT SUMMARY:' (that exact text, once), "
            "summarizing target users, core workflow, and must-have "
            "features in 2-3 sentences. " + CHAT_STYLE_RULE
        )
    else:
        system = (
            "Continue the Discovery Chat. Ask exactly ONE focused follow-up "
            "question to clarify scope. " + CHAT_STYLE_RULE
        )

    result = await ai_router.generate(ai_router.Feature.DISCOVERY_CHAT_NLU, history, system=system)
    state.messages.append(ChatMessage(role="assistant", text=result["text"]))
    if "CONCEPT SUMMARY:" in result["text"]:
        state.concept_summary = result["text"].split("CONCEPT SUMMARY:", 1)[1].strip()
        state.stage = "research"
    store.save_session(state)
    return state


@router.post("/research", response_model=SessionState)
async def run_research(req: ChatTurnRequest):
    """Kick off the competitive-research card once the concept is summarized.

    Runs a web-search-grounded deep-research pass (BRD/PRD Section 18.8
    amendment) -- market landscape by category, a viability/revenue verdict,
    demand signals, technical/legal risks, phased feature recommendations,
    and monetization models -- matching the depth of a manual
    Perplexity/Gemini research pass rather than a bare competitor list.
    """
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    basis = state.concept_summary or req.message

    result = await ai_router.generate(
        ai_router.Feature.COMPETITIVE_RESEARCH,
        f"{RESEARCH_FRAMING}\n\nMy idea: {basis}\n\n{RESEARCH_JSON_INSTRUCTIONS}",
        system=(
            "You are the Discovery Chat's competitive-research assistant. "
            "Use web search to verify every product you name actually "
            "exists and is currently operating -- do not invent products or "
            "cite discontinued ones. Be specific to the idea given, never "
            "generic. Output strict JSON only, per the schema in the prompt."
        ),
    )
    try:
        report, names = _parse_research_report(result["text"])
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Research JSON parse failed for session %s (%s) -- falling back "
            "to a flat viability note so the user still sees something "
            "rather than a 500. Raw response head: %r",
            state.session_id, exc, result["text"][:300],
        )
        report = ResearchReport(viability_verdict=_clean_line(result["text"])[:2000])
        names = []
    state.research = report
    state.companies = [
        f"{row.category}: {row.examples}" for row in report.market_landscape
    ]  # legacy flat field kept in sync for any old rendering path
    state.suggested_names = names or state.suggested_names
    store.save_session(state)
    return state


@router.post("/research/more", response_model=SessionState)
async def research_more(req: ResearchMoreRequest):
    """The 'search for more similar companies' continuation loop -- appends
    additional market-landscape rows grounded in the same web-search tool."""
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")

    existing = state.research or ResearchReport()
    already = ", ".join(f"{r.category} ({r.examples})" for r in existing.market_landscape)

    result = await ai_router.generate(
        ai_router.Feature.COMPETITIVE_RESEARCH,
        f"Product concept: {state.concept_summary}\n"
        f"Already found: {already or 'none yet'}\n"
        f"User's follow-up research request: {req.query}\n\n"
        "Use web search to find additional real, currently operating "
        "products/categories matching this follow-up request. Respond with "
        "ONLY a JSON object: "
        '{"market_landscape": [{"category": "...", "examples": "...", '
        '"what_they_do": "...", "limitations": "..."}]}. '
        "Do not repeat categories already found. No markdown fences.",
        system="You are the Discovery Chat's competitive-research assistant. Output strict JSON only.",
    )
    try:
        data = _extract_json_object(result["text"])
        new_rows = [
            MarketLandscapeRow(
                category=_clean_line(str(r.get("category", ""))),
                examples=_clean_line(str(r.get("examples", ""))),
                what_they_do=_clean_line(str(r.get("what_they_do", ""))),
                limitations=_clean_line(str(r.get("limitations", ""))),
            )
            for r in data.get("market_landscape", []) if isinstance(r, dict)
        ]
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "research/more JSON parse failed for session %s (%s) -- no rows "
            "appended this round rather than surfacing a 500.",
            state.session_id, exc,
        )
        new_rows = []

    existing.market_landscape.extend(new_rows)
    state.research = existing
    state.companies = [f"{row.category}: {row.examples}" for row in existing.market_landscape]
    store.save_session(state)
    return state


@router.post("/name-check", response_model=SessionState)
async def check_name(req: NameCheckRequest):
    """Custom brand-name availability check — non-critical NLU tier."""
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")

    result = await ai_router.generate(
        ai_router.Feature.NAME_AVAILABILITY_CHECK,
        f"Give a brief, plausible-sounding availability check for the brand "
        f"name '{req.name}' as a software product name (domain/trademark "
        f"style reasoning). One or two sentences.",
        system="You are a lightweight brand-name availability assistant. This is not a legal opinion.",
    )
    state.messages.append(ChatMessage(role="assistant", text=f"[{req.name}] {result['text']}"))
    store.save_session(state)
    return state


@router.post("/select-name", response_model=SessionState)
async def select_name(req: SelectNameRequest):
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    state.selected_name = req.name
    state.stage = "identity"
    store.save_session(state)
    return state


@router.post("/select-theme", response_model=SessionState)
async def select_theme(req: SelectThemeRequest):
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    state.selected_theme = req.theme
    state.stage = "freeze"
    store.save_session(state)
    return state


@router.get("/{session_id}", response_model=SessionState)
async def get_session(session_id: str):
    state = store.get_session(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    return state
