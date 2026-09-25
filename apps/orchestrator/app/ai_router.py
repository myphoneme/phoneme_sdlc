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


class AIRouterError(Exception):
    pass


async def _call_ollama(prompt: str, system: str | None = None) -> str:
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


async def _call_anthropic(prompt: str, system: str | None = None) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise AIRouterError("ANTHROPIC_API_KEY not configured")
    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        try:
            return "".join(block["text"] for block in data["content"] if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise AIRouterError(f"Unexpected Anthropic response shape: {data!r}") from exc


async def _call_gemini(prompt: str, system: str | None = None) -> str:
    if not config.GEMINI_API_KEY:
        raise AIRouterError("GEMINI_API_KEY not configured")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    payload = {"contents": contents}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIRouterError(f"Unexpected Gemini response shape: {data!r}") from exc


async def _call_astra(prompt: str, system: str | None = None) -> str:
    # Placeholder — provider unconfirmed (TDD Section 9 open item). Wired so
    # that once ASTRA_API_URL/ASTRA_API_KEY are set, this becomes a real call
    # without touching any caller.
    if not (config.ASTRA_API_URL and config.ASTRA_API_KEY):
        raise AIRouterError("Astra endpoint not configured (provider TBD — see TDD Section 9)")
    raise AIRouterError("Astra client not yet implemented — provider confirmation pending")


_COMMERCIAL_BACKENDS = {
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
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
        try:
            text = await backend(prompt, system)
            return {"text": text, "tier": "commercial", "model": config.COMMERCIAL_PROVIDER, "fallback": False}
        except AIRouterError as exc:
            logger.warning(
                "Commercial tier unavailable for critical feature %s (%s) — "
                "falling back to Ollama for local/dev only. This must not "
                "happen on staging without an explicit tier downgrade.",
                feature.value, exc,
            )
            text = await _call_ollama(prompt, system)
            return {"text": text, "tier": "ollama", "model": config.OLLAMA_MODEL, "fallback": True}
    else:
        text = await _call_ollama(prompt, system)
        return {"text": text, "tier": "ollama", "model": config.OLLAMA_MODEL, "fallback": False}
