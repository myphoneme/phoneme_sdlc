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
from ..locks import session_lock
from ..models import (
    StartSessionRequest, ChatTurnRequest, ResearchMoreRequest,
    NameCheckRequest, SelectNameRequest, SelectThemeRequest, SessionState,
    ChatMessage, MarketLandscapeRow, ResearchReport, ConceptBrief,
    ConfirmBriefRequest, SessionRequest,
)

logger = logging.getLogger("phoneme.discovery")

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

# Discovery chat is force-terminated after this many user turns rather than
# trusting the model to volunteer a 'CONCEPT SUMMARY:' on its own — verified
# against the real AI server (2026-09-25) that it will otherwise keep asking
# open-ended clarifying questions indefinitely (headers, numbered lists,
# multi-part probes) instead of converging. One user turn from /start plus
# this many more /chat turns, then the next /chat call is forced to summarize.
# 2026-09-30 dry run: 1 turn locked RelayReel's concept after a single
# question -- target users, market and launch platforms were never asked,
# and the private/public choice the user stated was dropped. Up to 3
# clarifying turns now, steered by DISCOVERY_CHECKLIST, and the user can end
# early with "Summarise now" (/summarize). The summary is then shown as an
# editable ConceptBrief (stage 'confirm') before research spends money.
MAX_CLARIFYING_TURNS = 3

DISCOVERY_CHECKLIST = (
    "Across the conversation you need clear answers to: (1) who the target "
    "users are, (2) how content/data gets into the product (input "
    "channels), (3) privacy/visibility -- what is private vs. shared or "
    "public, (4) the launch market and language(s), (5) which platforms "
    "ship first (web, iOS, Android, WhatsApp, etc.). Ask about the most "
    "important item that is still unclear. Never re-ask something the user "
    "already answered."
)

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
  "positioning_reframe": "<the naive/generic way someone would describe this idea, then the sharper, more valuable and more defensible way to position it instead -- one crisp paragraph contrasting the two>",
  "killer_feature": "<the single standout feature or UX moment that should be the product's central hook -- name it, then 2-3 sentences on why it's the differentiator and roughly how it would work>",
  "suggested_names": ["<3 short, brandable product name candidates specific to this concept>"],
  "sources": ["<a real URL you actually consulted via web search for this research -- only include URLs you genuinely retrieved, never fabricate one>"]
}

Requirements:
- market_landscape must have 3-6 rows covering distinct tool categories that
  actually compete with or adjoin this idea -- use web search to find REAL
  products, not invented ones. If you cannot verify a product exists, omit it.
- Every list should be specific to THIS product concept, not generic SaaS
  advice that would apply to any idea.
- recommended_features should total 6-12 items across phases.
- positioning_reframe and killer_feature must be genuinely sharp, specific
  insight, not a restatement of the concept -- if the obvious framing is
  already the best framing, say so briefly rather than manufacturing a fake
  reframe.
- suggested_names must be plausible brand names for THIS concept -- never
  reuse a competitor's name.
- sources should list the real URLs your web search actually returned (aim
  for 4-8 across the whole response). Only include a URL if it came from an
  actual search result -- never invent or guess one. If no web search was
  used for this response, return an empty list rather than fabricating URLs.
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
        positioning_reframe=_clean_line(str(data.get("positioning_reframe", ""))),
        killer_feature=_clean_line(str(data.get("killer_feature", ""))),
        sources=[_clean_line(str(x)) for x in data.get("sources", []) if isinstance(x, str) and x.strip()],
    ), [_clean_line(str(x)) for x in data.get("suggested_names", [])]


@router.post("/start", response_model=SessionState)
async def start_session(req: StartSessionRequest):
    state = await store.new_session()
    state.messages.append(ChatMessage(role="user", text=req.initial_message))

    result = await ai_router.generate(
        ai_router.Feature.DISCOVERY_CHAT_NLU,
        req.initial_message,
        system=(
            "You are the Phoneme SDLC Platform's Discovery Chat assistant. "
            "The user is describing a new product idea. Reflect back your "
            "understanding of the target users, the core workflow, and the "
            "problem it solves, then ask exactly ONE focused follow-up "
            "question to clarify scope. " + DISCOVERY_CHECKLIST + " " + CHAT_STYLE_RULE
        ),
    )
    state.messages.append(ChatMessage(role="assistant", text=result["text"]))
    await store.save_session(state)
    return state


SUMMARY_SYSTEM = (
    "Enough has been shared to scope this product. Do NOT ask any further "
    "questions. Respond with ONLY one paragraph, prefixed exactly with "
    "'CONCEPT SUMMARY:' (that exact text, once), summarizing target users, "
    "core workflow, input channels, privacy/visibility choices and "
    "must-have features in 3-4 sentences. Keep every decision the user "
    "stated -- do not drop or override any of them. " + CHAT_STYLE_RULE
)

BRIEF_JSON = """Respond with ONLY one JSON object, no markdown fences:
{
  "summary": "<2-3 sentence plain-language concept summary>",
  "target_users": "<who it is for, as the user described them>",
  "core_workflow": "<the main loop, in one or two sentences>",
  "input_channels": "<how content/data enters the product>",
  "privacy_mode": "<what is private vs shared/public, as the user stated>",
  "market": "<launch market / geography / language>",
  "platforms": "<which platforms ship first>",
  "must_haves": ["<must-have capability>"],
  "out_of_scope": ["<explicitly excluded or deferred>"],
  "assumptions": ["<anything you had to ASSUME because the user did not say it -- phrase as 'Assumed: ...'>"]
}
Only use what the user actually said for every field except assumptions. If
the user did not state a field, write "Not stated" and add a matching entry
to assumptions describing a sensible default. Never invent a decision."""


async def _summarize_and_brief(state: SessionState) -> None:
    """Close Discovery: free-text summary for the chat log, then a
    structured brief the user confirms/edits on the next screen."""
    history = "\n".join(f"{m.role}: {m.text}" for m in state.messages)
    result = await ai_router.generate(ai_router.Feature.DISCOVERY_CHAT_NLU, history, system=SUMMARY_SYSTEM)
    text = result["text"]
    if "CONCEPT SUMMARY:" not in text:
        text = "CONCEPT SUMMARY: " + text.strip()
    state.messages.append(ChatMessage(role="assistant", text=text))
    summary = text.split("CONCEPT SUMMARY:", 1)[1].strip()

    brief = ConceptBrief(summary=summary)
    try:
        b = await ai_router.generate(
            ai_router.Feature.CONCEPT_BRIEF,
            f"Discovery conversation:\n{history}\n\n{BRIEF_JSON}",
            system="You turn a product discovery conversation into a structured, faithful concept brief.",
        )
        data = _extract_json_object(b["text"])
        def _s(k):
            return _clean_line(str(data.get(k, "") or ""))
        def _l(k):
            return [_clean_line(str(x)) for x in (data.get(k) or []) if str(x).strip()]
        brief = ConceptBrief(
            summary=_s("summary") or summary,
            target_users=_s("target_users"), core_workflow=_s("core_workflow"),
            input_channels=_s("input_channels"), privacy_mode=_s("privacy_mode"),
            market=_s("market"), platforms=_s("platforms"),
            must_haves=_l("must_haves"), out_of_scope=_l("out_of_scope"),
            assumptions=_l("assumptions"),
        )
    except Exception as exc:  # brief is an aid; never block the user on it
        logger.warning("Concept brief extraction failed for %s: %s", state.session_id, exc)
    state.concept_brief = brief
    state.concept_summary = summary
    state.stage = "confirm"


@router.post("/chat", response_model=SessionState)
async def chat_turn(req: ChatTurnRequest):
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if state.stage != "discovery":
        raise HTTPException(409, "discovery is already complete for this idea")

    user_turns_so_far = sum(1 for m in state.messages if m.role == "user")
    state.messages.append(ChatMessage(role="user", text=req.message))

    if user_turns_so_far >= MAX_CLARIFYING_TURNS:
        await _summarize_and_brief(state)
    else:
        history = "\n".join(f"{m.role}: {m.text}" for m in state.messages)
        system = (
            "Continue the Discovery Chat. " + DISCOVERY_CHECKLIST + " If every "
            "item is already clear, instead reply with ONLY a paragraph "
            "prefixed 'CONCEPT SUMMARY:'. Otherwise ask exactly ONE focused "
            "follow-up question. " + CHAT_STYLE_RULE
        )
        result = await ai_router.generate(ai_router.Feature.DISCOVERY_CHAT_NLU, history, system=system)
        if "CONCEPT SUMMARY:" in result["text"]:
            await _summarize_and_brief(state)
        else:
            state.messages.append(ChatMessage(role="assistant", text=result["text"]))
    await store.save_session(state)
    return state


@router.post("/summarize", response_model=SessionState)
async def summarize_now(req: SessionRequest):
    """User pressed 'Summarise now' -- close Discovery with what we have."""
    async with session_lock(req.session_id, "summarize"):
        state = await store.get_session(req.session_id)
        if not state:
            raise HTTPException(404, "session not found")
        if state.stage != "discovery":
            return state
        await _summarize_and_brief(state)
        await store.save_session(state)
        return state


def _brief_to_summary(b: ConceptBrief) -> str:
    """The confirmed brief becomes the concept text every later prompt
    reads, so stated decisions (privacy mode, market, platforms) reach
    research, module breakdown, flows and the BRD/PRD."""
    parts = [b.summary.strip()]
    for label, val in (
        ("Target users", b.target_users), ("Core workflow", b.core_workflow),
        ("Input channels", b.input_channels), ("Privacy / visibility", b.privacy_mode),
        ("Launch market", b.market), ("Launch platforms", b.platforms),
    ):
        if val and val.strip() and val.strip().lower() != "not stated":
            parts.append(f"{label}: {val.strip()}")
    if b.must_haves:
        parts.append("Must-haves: " + "; ".join(b.must_haves))
    if b.out_of_scope:
        parts.append("Out of scope: " + "; ".join(b.out_of_scope))
    return "\n".join(p for p in parts if p)


@router.post("/confirm", response_model=SessionState)
async def confirm_brief(req: ConfirmBriefRequest):
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if state.stage not in ("confirm", "discovery"):
        return state
    state.concept_brief = req.brief
    state.concept_summary = _brief_to_summary(req.brief)
    state.stage = "research"
    await store.save_session(state)
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
    async with session_lock(req.session_id, "research"):
        state = await store.get_session(req.session_id)
        if not state:
            raise HTTPException(404, "session not found")
        if state.research is not None:
            # Another tab already ran it -- never pay for research twice.
            return state
        return await _run_research(state, req.message)


async def _run_research(state: SessionState, fallback_basis: str) -> SessionState:
    basis = state.concept_summary or fallback_basis

    result = await ai_router.generate(
        ai_router.Feature.COMPETITIVE_RESEARCH,
        f"{RESEARCH_FRAMING}\n\nMy idea: {basis}\n\n{RESEARCH_JSON_INSTRUCTIONS}",
        system=(
            "You are the Discovery Chat's competitive-research assistant. "
            "Use web search to verify every product you name actually "
            "exists and is currently operating -- do not invent products or "
            "cite discontinued ones. Be specific to the idea given, never "
            "generic. Quote prices in the currency of the stated launch "
            "market (e.g. INR for India), with USD in brackets where useful. "
            "Output strict JSON only, per the schema in the prompt."
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
    await store.save_session(state)
    return state


@router.post("/research/more", response_model=SessionState)
async def research_more(req: ResearchMoreRequest):
    """The 'search for more similar companies' continuation loop -- appends
    additional market-landscape rows grounded in the same web-search tool."""
    state = await store.get_session(req.session_id)
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
        '"what_they_do": "...", "limitations": "..."}], '
        '"sources": ["<real URL actually consulted via web search, if any>"]}. '
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
        new_sources = [_clean_line(str(x)) for x in data.get("sources", []) if isinstance(x, str) and x.strip()]
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "research/more JSON parse failed for session %s (%s) -- no rows "
            "appended this round rather than surfacing a 500.",
            state.session_id, exc,
        )
        new_rows = []
        new_sources = []

    existing.market_landscape.extend(new_rows)
    for s in new_sources:
        if s not in existing.sources:
            existing.sources.append(s)
    state.research = existing
    state.companies = [f"{row.category}: {row.examples}" for row in existing.market_landscape]
    await store.save_session(state)
    return state


@router.post("/research/done", response_model=SessionState)
async def research_done(req: SessionRequest):
    """Research reviewed -- move on to Identity, where the name, domains,
    tagline, colour theme and logo are chosen (2026-09-30: naming moved out
    of Research into its own Identity studio)."""
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    if state.stage == "research":
        state.stage = "identity"
        await store.save_session(state)
    return state


@router.post("/name-check", response_model=SessionState)
async def check_name(req: NameCheckRequest):
    """Custom brand-name availability check — non-critical NLU tier."""
    state = await store.get_session(req.session_id)
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
    await store.save_session(state)
    return state


@router.post("/select-name", response_model=SessionState)
async def select_name(req: SelectNameRequest):
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    state.selected_name = req.name
    state.stage = "identity"
    await store.save_session(state)
    return state


@router.post("/select-theme", response_model=SessionState)
async def select_theme(req: SelectThemeRequest):
    state = await store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    state.selected_theme = req.theme
    state.stage = "freeze"
    await store.save_session(state)
    return state


@router.get("")
async def list_sessions():
    """Summary rows for the GiveWings dashboard's product grid. Defined
    ahead of GET /{session_id} below (both route decorators sit on this same
    `router`, prefixed with /api/discovery) so Starlette resolves an exact
    '/api/discovery' request to this handler rather than ever trying to
    match it against the {session_id} path parameter route."""
    return await store.list_sessions()


@router.get("/{session_id}", response_model=SessionState)
async def get_session(session_id: str):
    state = await store.get_session(session_id)
    if not state:
        raise HTTPException(404, "session not found")
    return state
