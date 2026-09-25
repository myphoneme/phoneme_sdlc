"""
Stage 1 (Discovery Chat) and Stage 2 (User Flow / Identity) endpoints.

Ports the onboarding-wizard-mock.html flow onto real backend calls, routed
through ai_router per the frozen model policy: discovery-chat NLU and the
custom-name check are non-critical (Ollama); competitive-research
summarization and the eventual module breakdown are critical (commercial).
"""
from fastapi import APIRouter, HTTPException

from .. import ai_router, store
from ..models import (
    StartSessionRequest, ChatTurnRequest, ResearchMoreRequest,
    NameCheckRequest, SelectNameRequest, SelectThemeRequest, SessionState,
    ChatMessage,
)

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
    """Kick off the competitive-research card once the concept is summarized."""
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")
    basis = state.concept_summary or req.message

    result = await ai_router.generate(
        ai_router.Feature.COMPETITIVE_RESEARCH,
        f"Product concept: {basis}\n\n"
        "List 3-5 real or representative companies/products that compete in "
        "this space, one per line, as 'Name — one-line differentiator'.",
        system="You are the Discovery Chat's competitive-research assistant.",
    )
    lines = [l.strip("-• ").strip() for l in result["text"].splitlines() if l.strip()]
    state.companies = lines[:5]
    store.save_session(state)
    return state


@router.post("/research/more", response_model=SessionState)
async def research_more(req: ResearchMoreRequest):
    """The 'search for more similar companies' continuation loop."""
    state = store.get_session(req.session_id)
    if not state:
        raise HTTPException(404, "session not found")

    result = await ai_router.generate(
        ai_router.Feature.COMPETITIVE_RESEARCH,
        f"Product concept: {state.concept_summary}\n"
        f"Already found: {', '.join(state.companies)}\n"
        f"User's follow-up research request: {req.query}\n\n"
        "Return additional companies/products matching the request, one per "
        "line, as 'Name — one-line differentiator'. Do not repeat entries "
        "already found.",
        system="You are the Discovery Chat's competitive-research assistant.",
    )
    new_lines = [l.strip("-• ").strip() for l in result["text"].splitlines() if l.strip()]
    state.companies.extend(new_lines)
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
