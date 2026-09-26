#!/usr/bin/env bash
# Phoneme SDLC Platform — API key sanity check
#
# Verifies each commercial-tier API key actually authenticates, using a
# free or near-free endpoint per provider (never a paid generation/search
# call). Prints only OK/FAIL per provider plus the HTTP status -- it never
# prints the key itself, so its output is safe to paste back into chat.
#
# Usage: run this ON STAGING, from the orchestrator directory so it can
# find .env (or export the vars yourself first):
#   cd /home/project/phoneme_sdlc/apps/orchestrator
#   ../../scripts/check-api-keys.sh
# (or, if you copied it elsewhere, just run it -- it looks for .env in the
# orchestrator directory relative to itself, and falls back to whatever is
# already in the shell's environment.)

set -uo pipefail

# Locate and source .env without printing it.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for candidate in \
  "./.env" \
  "$SCRIPT_DIR/../apps/orchestrator/.env" \
  "/home/project/phoneme_sdlc/apps/orchestrator/.env"
do
  if [ -f "$candidate" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$candidate"
    set +a
    echo "==> Loaded env from: $candidate"
    break
  fi
done

pass=0
fail=0
skip=0

check() {
  local name="$1" status="$2"
  if [ "$status" = "SKIP" ]; then
    echo "  [SKIP] $name -- no key set"
    skip=$((skip + 1))
  elif [ "$status" -ge 200 ] && [ "$status" -lt 300 ]; then
    echo "  [ OK ] $name -- HTTP $status"
    pass=$((pass + 1))
  elif [ "$status" = "401" ] || [ "$status" = "403" ]; then
    echo "  [FAIL] $name -- HTTP $status (key present but rejected -- check it's correct and not revoked)"
    fail=$((fail + 1))
  else
    echo "  [FAIL] $name -- HTTP $status (unexpected -- check network/provider status)"
    fail=$((fail + 1))
  fi
}

echo "==> Checking commercial-tier API keys (no generation calls made, no keys printed)"
echo

# --- Anthropic ---
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    "https://api.anthropic.com/v1/models")
  check "Anthropic (ANTHROPIC_API_KEY)" "$status"
else
  check "Anthropic (ANTHROPIC_API_KEY)" "SKIP"
fi

# --- Gemini ---
if [ -n "${GEMINI_API_KEY:-}" ]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY")
  check "Gemini (GEMINI_API_KEY)" "$status"
else
  check "Gemini (GEMINI_API_KEY)" "SKIP"
fi

# --- OpenAI ---
if [ -n "${OPENAI_API_KEY:-}" ]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    "https://api.openai.com/v1/models")
  check "OpenAI (OPENAI_API_KEY)" "$status"
else
  check "OpenAI (OPENAI_API_KEY)" "SKIP"
fi

echo
echo "==> Active COMMERCIAL_PROVIDER: ${COMMERCIAL_PROVIDER:-anthropic (default)}"
echo "==> Summary: $pass OK, $fail FAIL, $skip not configured"

if [ "$fail" -gt 0 ]; then
  exit 1
fi
exit 0
