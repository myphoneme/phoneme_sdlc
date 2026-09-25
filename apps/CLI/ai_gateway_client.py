"""
Phoneme SDLC Platform - AI Server client
Calls the Ollama (OpenAI-compatible) chat completions endpoint on the AI server
via a POST request, following the same request/response shape the platform's
discovery-chat and document-generation skills will use.

Run directly on a machine that has network access to the AI server
(the AI server itself, the staging server, or a machine on the same
internal network) - this sandbox cannot reach 10.100.60.121, so it has
not been executed against the live server.

Usage:
    python3 ai_gateway_client.py                      # interactive prompt
    python3 ai_gateway_client.py "your prompt here"    # one-shot from argv
"""

import os
import sys
import requests

# Configurable via environment variable so the same script works
# unchanged across dev / staging / any future AI server address,
# without editing code per environment.
GATEWAY_URL = os.environ.get(
    "AI_GATEWAY_URL", "http://10.100.60.121:8000/v1/chat/completions"
)
MODEL = os.environ.get("AI_GATEWAY_MODEL", "gemma4:e4b")
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("AI_GATEWAY_TIMEOUT", "120"))


def chat_completion(prompt: str, model: str = MODEL, timeout: int = REQUEST_TIMEOUT_SECONDS) -> str:
    """
    POST a single-turn chat completion request to the AI gateway and
    return the model's reply text.

    Raises requests.exceptions.RequestException on any network/HTTP
    failure (timeout, connection refused, non-2xx status, malformed
    response) so callers can decide how to handle/report it - this
    function does not swallow errors.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    response = requests.post(GATEWAY_URL, json=payload, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise requests.exceptions.RequestException(
            f"Unexpected response shape from gateway: {data!r}"
        ) from exc


def main() -> int:
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = input("Enter your prompt: ")

    if not prompt.strip():
        print("No prompt given.")
        return 1

    print(f"POST {GATEWAY_URL}  (model={MODEL})")
    try:
        reply = chat_completion(prompt)
        print(reply)
        return 0
    except requests.exceptions.RequestException as exc:
        print(f"Gateway request failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
