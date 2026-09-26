#!/usr/bin/env bash
# Phoneme SDLC Platform — API key + credits sanity check
#
# Two passes per configured provider:
#   1. Auth check   -- free list-models call. Confirms the key is valid.
#   2. Credit check -- the smallest possible real generation call (1-5
#      output tokens, no web search). This is the only way to actually
#      exercise the billing path -- a key can authenticate fine and still
#      be rejected at generation time with "insufficient credits" /
#      "insufficient_quota" if there's no balance behind it. Costs a
#      fraction of a cent per provider, not free, but effectively
#      negligible (a few output tokens at standard token rates).
#
# Never prints the key itself -- only OK/FAIL + HTTP status + (on failure)
# a short excerpt of the provider's own error message, so this output is
# safe to paste back into chat for diagnosis.
#
# Usage: run this ON STAGING, from anywhere -- it looks for .env in the
# orchestrator directory relative to itself, then a few likely paths, then
# falls back to whatever is already in the shell's environment:
#   cd /home/project/phoneme_sdlc/apps/orchestrator
#   ../../scripts/check-api-keys.sh
#   ../../scripts/check-api-keys.sh --auth-only   # skip the paid generation calls

set -uo pipefail

AUTH_ONLY=false
[ "${1:-}" = "--auth-only" ] && AUTH_ONLY=true

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

# excerpt <body> -- pulls a short, key-safe snippet of an error message for
# display. Strips anything that looks like it could be a credential.
excerpt() {
  echo "$1" | head -c 300 | tr '\n' ' ' | sed -E 's/"(key|api_key|x-api-key|authorization)"\s*:\s*"[^"]*"/"\1":"[redacted]"/gi'
}

auth_check() {
  local name="$1" status="$2"
  if [ "$status" = "SKIP" ]; then
    echo "  [SKIP] $name -- no key set"
    skip=$((skip + 1)); return 1
  elif [ "$status" -ge 200 ] && [ "$status" -lt 300 ]; then
    echo "  [ OK ] $name auth -- HTTP $status"
    return 0
  elif [ "$status" = "401" ] || [ "$status" = "403" ]; then
    echo "  [FAIL] $name auth -- HTTP $status (key rejected -- wrong or revoked)"
    fail=$((fail + 1)); return 1
  else
    echo "  [FAIL] $name auth -- HTTP $status (unexpected)"
    fail=$((fail + 1)); return 1
  fi
}

credit_check() {
  local name="$1" status="$2" body="$3"
  if [ "$status" -ge 200 ] && [ "$status" -lt 300 ]; then
    echo "  [ OK ] $name generation -- HTTP $status (credits available)"
    pass=$((pass + 1))
  else
    local lower
    lower=$(echo "$body" | tr '[:upper:]' '[:lower:]')
    if echo "$lower" | grep -qE "credit|insufficient_quota|billing|quota exceeded|resource_exhausted"; then
      echo "  [FAIL] $name generation -- HTTP $status (looks like NO CREDITS / billing issue)"
      echo "         $(excerpt "$body")"
    else
      echo "  [FAIL] $name generation -- HTTP $status (not obviously a credits issue -- see message)"
      echo "         $(excerpt "$body")"
    fi
    fail=$((fail + 1))
  fi
}

echo "==> Checking commercial-tier API keys"
echo "==> Pass 1: auth (free). Pass 2: smallest real generation call (near-zero cost) to confirm credits."
echo

# ================= Anthropic =================
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" \
    "https://api.anthropic.com/v1/models")
  if auth_check "Anthropic" "$status" && [ "$AUTH_ONLY" = false ]; then
    resp=$(curl -s -w "\n%{http_code}" \
      -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
      -d "{\"model\":\"${ANTHROPIC_MODEL:-claude-sonnet-5}\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" \
      "https://api.anthropic.com/v1/messages")
    gstatus=$(echo "$resp" | tail -n1); gbody=$(echo "$resp" | sed '$d')
    credit_check "Anthropic" "$gstatus" "$gbody"
  fi
else
  auth_check "Anthropic" "SKIP"
fi
echo

# ================= Gemini =================
if [ -n "${GEMINI_API_KEY:-}" ]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY")
  if auth_check "Gemini" "$status" && [ "$AUTH_ONLY" = false ]; then
    resp=$(curl -s -w "\n%{http_code}" -H "content-type: application/json" \
      -d "{\"contents\":[{\"role\":\"user\",\"parts\":[{\"text\":\"hi\"}]}],\"generationConfig\":{\"maxOutputTokens\":1}}" \
      "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL:-gemini-2.5-pro}:generateContent?key=$GEMINI_API_KEY")
    gstatus=$(echo "$resp" | tail -n1); gbody=$(echo "$resp" | sed '$d')
    credit_check "Gemini" "$gstatus" "$gbody"
  fi
else
  auth_check "Gemini" "SKIP"
fi
echo

# ================= OpenAI =================
if [ -n "${OPENAI_API_KEY:-}" ]; then
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    "https://api.openai.com/v1/models")
  if auth_check "OpenAI" "$status" && [ "$AUTH_ONLY" = false ]; then
    resp=$(curl -s -w "\n%{http_code}" \
      -H "Authorization: Bearer $OPENAI_API_KEY" -H "content-type: application/json" \
      -d "{\"model\":\"${OPENAI_MODEL:-gpt-5.1}\",\"input\":\"hi\",\"max_output_tokens\":16}" \
      "https://api.openai.com/v1/responses")
    gstatus=$(echo "$resp" | tail -n1); gbody=$(echo "$resp" | sed '$d')
    credit_check "OpenAI" "$gstatus" "$gbody"
  fi
else
  auth_check "OpenAI" "SKIP"
fi

echo
echo "==> Active COMMERCIAL_PROVIDER: ${COMMERCIAL_PROVIDER:-anthropic (default)}"
echo "==> Summary: $pass OK, $fail FAIL, $skip not configured"
[ "$AUTH_ONLY" = true ] && echo "==> (ran with --auth-only: credits were NOT checked)"

[ "$fail" -gt 0 ] && exit 1
exit 0
