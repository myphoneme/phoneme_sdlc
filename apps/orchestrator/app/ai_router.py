"""
Phoneme SDLC Platform — AI Model Router.

Implements the routing policy frozen in BRD/PRD Section 18.8 and Technical
Design Document (PHN-PSP-2026-02-TDD) Section 8: critical, accuracy-sensitive
generation goes to a commercial model; non-critical NLU goes to the local
Ollama model on the AI server. This module is the single place that decision
is implemented — callers ask for a `feature`, not a model or a tier.

If a commercial API key isn't configured (local/dev), critical features fall
back to Ollama with a warning, so the app still runs end-to-end without
commercial credentials — but this fallback must never happen on staging for
a feature marked critical without the tier being explicitly downgraded.
"""
import logging
from enum import Enum

import httpx

from . import config

logger = logging.getLogger("phoneme.ai_router")


class Feature(str, Enum):
    # Critical — commercial tier (BRD/PRD Section 18.8)
    BRD_PRD_DRAFTING = "brd_prd_drafting"
    TECH_DESIGN_GENERATION = "tech_design_generation"
    REGENERATE_FROM_COMMENTS = "regenerate_from_comments"
    MODULE_BREAKDOWN = "module_breakdown"
    COMPETITIVE_RESEARCH = "competitive_research"
    # Non-critical — Ollama tier (BRD/PRD Section 18.8)
    DISCOVERY_CHAT_NLU = "discovery_chat_nlu"
    NAME_AVAILABILITY_CHECK = "name_availability_check"


CRITICAL_FEATURES = {
    Feature.BRD_PRD_DRAFTING,
    Feature.TECH_DESIGN_GENERATION,
    Feature.REGENERATE_FROM_COMMENTS,
    Feature.MODULE_BREAKDOWN,
    Feature.COMPETITIVE_RESEARCH,
}

# Features that should be answered with live web-search grounding rather
# than the model's training-data recall alone -- these are the two steps
# where "what actually exists on the market right now" materially changes
# the output (BRD/PRD Section 18.8 amendment, 2026-09-26: grounding added
# after staging validation showed un-grounded research degrading to generic
# SaaS names unrelated to the product concept).
SEARCH_GROUNDED_FEATURES = {
    Feature.COMPETITIVE_RESEARCH,
    Feature.MODULE_BREAKDOWN,
}


class AIRouterError(Exception):
    pass


async def _call_ollama(prompt: str, system: str | None = None, use_search: bool = False) -> str:
    # use_search is accepted-and-ignored: Ollama here has no web-search tool
    # wired up. Kept in the signature so _call_ollama can be swapped in
    # wherever a _COMMERCIAL_BACKENDS-shaped callable is expected without a
    # TypeError on the use_search kwarg.
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": config.OLLAMA_MODEL, "messages": messages, "stream": False}
    async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT_SECONDS) as client:
        resp = await client.post(config.OLLAMA_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIRouterError(f"Unexpected Ollama response shape: {data!r}") from exc


async def _call_anthropic(prompt: str, system: str | None = None, use_search: bool = False) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise AIRouterError("ANTHROPIC_API_KEY not configured")
    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": config.ANTHROPIC_MODEL,
        # Search-grounded calls return a lot more structured content
        # (market tables, phased feature lists, citations) than a plain
        # generation -- give them more room than the 2048-token default.
        "max_tokens": 4096 if use_search else 2048,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    if use_search:
        # Native Claude web-search tool -- $10 per 1,000 searches + token
        # cost, no special API tier required. Claude decides when to issue
        # a search; results (with source URLs) are folded into its own
        # context before it writes the final answer.
        payload["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]
    async with httpx.AsyncClient(timeout=90 if use_search else 60) as client:
        resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        try:
            # A search-grounded response's `content` list interleaves text
            # blocks with server_tool_use/web_search_tool_result blocks for
            # each search Claude ran -- concatenating only the `text` blocks
            # (as before) already gives the final synthesized answer and
            # skips the intermediate tool-call bookkeeping.
            return "".join(block["text"] for block in data["content"] if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise AIRouterError(f"Unexpected Anthropic response shape: {data!r}") from exc


async def _call_gemini(prompt: str, system: str | None = None, use_search: bool = False) -> str:
    if not config.GEMINI_API_KEY:
        raise AIRouterError("GEMINI_API_KEY not configured")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    payload = {"contents": contents}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if use_search:
        # Grounding with Google Search -- 5,000 free requests/month on
        # Gemini 3.x then ~$14/1,000 queries; no special tier needed beyond
        # a configured GEMINI_API_KEY. Keeps research grounded regardless of
        # which commercial provider staging is pointed at (this must not be
        # an Anthropic-only capability).
        payload["tools"] = [{"google_search": {}}]
    async with httpx.AsyncClient(timeout=90 if use_search else 60) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        try:
            # Grounded responses can come back as multiple parts (the model
            # may interleave search-driven segments); join every text part
            # rather than assuming a single parts[0].
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p["text"] for p in parts if "text" in p)
        except (KeyError, IndexError, TypeError) as exc:
            raise AIRouterError(f"Unexpected Gemini response shape: {data!r}") from exc


async def _call_openai(prompt: str, system: str | None = None, use_search: bool = False) -> str:
    if not config.OPENAI_API_KEY:
        raise AIRouterError("OPENAI_API_KEY not configured")
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "content-type": "application/json",
    }
    # Responses API (not Chat Completions) -- required for the hosted
    # web_search tool. $10/1,000 calls, same pricing shape as Claude's
    # web_search tool and priced identically per OpenAI's published rates
    # (added 2026-09-26 as a third search-grounded backend option).
    payload = {"model": config.OPENAI_MODEL, "input": prompt}
    if system:
        payload["instructions"] = system
    if use_search:
        payload["tools"] = [{"type": "web_search"}]
    async with httpx.AsyncClient(timeout=90 if use_search else 60) as client:
        resp = await client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        try:
            # The Responses API returns a list of output items -- web_search
            # calls, reasoning items, and one or more "message" items whose
            # own content list holds the actual "output_text" blocks. Join
            # every output_text block across every message item, mirroring
            # how the Anthropic/Gemini extraction skips non-text blocks.
            texts = [
                block.get("text", "")
                for item in data.get("output", [])
                if item.get("type") == "message"
                for block in item.get("content", [])
                if block.get("type") == "output_text"
            ]
            if not texts:
                raise KeyError("no output_text blocks in response")
            return "".join(texts)
        except (KeyError, IndexError, TypeError) as exc:
            raise AIRouterError(f"Unexpected OpenAI response shape: {data!r}") from exc


async def _call_astra(prompt: str, system: str | None = None, use_search: bool = False) -> str:
    # Placeholder — provider unconfirmed (TDD Section 9 open item). Wired so
    # that once ASTRA_API_URL/ASTRA_API_KEY are set, this becomes a real call
    # without touching any caller.
    if not (config.ASTRA_API_URL and config.ASTRA_API_KEY):
        raise AIRouterError("Astra endpoint not configured (provider TBD — see TDD Section 9)")
    raise AIRouterError("Astra client not yet implemented — provider confirmation pending")


_COMMERCIAL_BACKENDS = {
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
    "openai": _call_openai,
    "astra": _call_astra,
}


async def generate(feature: Feature, prompt: str, system: str | None = None) -> dict:
    """
    Route a generation request per the feature-criticality policy.

    Returns {"text": str, "tier": "commercial"|"ollama", "model": str, "fallback": bool}
    so callers/UI can surface which tier actually served the request —
    important during the pilot while commercial keys may not be configured.
    """
    if feature in CRITICAL_FEATURES:
        backend = _COMMERCIAL_BACKENDS.get(config.COMMERCIAL_PROVIDER, _call_anthropic)
        use_search = feature in SEARCH_GROUNDED_FEATURES and config.COMMERCIAL_PROVIDER in ("anthropic", "gemini", "openai")
        try:
            text = await backend(prompt, system, use_search=use_search)
            return {
                "text": text, "tier": "commercial", "model": config.COMMERCIAL_PROVIDER,
                "fallback": False, "grounded": use_search,
            }
        except (AIRouterError, httpx.HTTPError) as exc:
            # httpx.HTTPError covers HTTPStatusError (non-2xx from the
            # provider, e.g. rate limit/auth/server errors) and network-level
            # failures (timeout, connect error) raised by resp.raise_for_status()
            # and the request itself inside _call_anthropic/_call_gemini --
            # neither of which is an AIRouterError. Without catching these too,
            # a transient commercial-tier failure bypasses the fallback below
            # entirely and surfaces to the caller as a raw unhandled 500.
            logger.warning(
                "Commercial tier unavailable for critical feature %s (%s: %s) — "
                "falling back to Ollama for local/dev only. This must not "
                "happen on staging without an explicit tier downgrade.",
                feature.value, type(exc).__name__, exc,
            )
            try:
                text = await _call_ollama(prompt, system)
                return {"text": text, "tier": "ollama", "model": config.OLLAMA_MODEL, "fallback": True}
            except Exception:
                logger.exception(
                    "Ollama fallback also failed for critical feature %s after "
                    "commercial tier error (%s: %s)",
                    feature.value, type(exc).__name__, exc,
                )
                raise
    else:
        text = await _call_ollama(prompt, system)
        return {"text": text, "tier": "ollama", "model": config.OLLAMA_MODEL, "fallback": False}
