# Phoneme SDLC Platform — Backend

FastAPI backend for the Idea-to-BRD/PRD Wizard, implementing the AI model
routing policy frozen in the Technical Design Document
(`docs/02-technical-design/Phoneme_SDLC_Platform_TDD_v1.0.docx`, Section 8).

## Local run

```bash
cd src/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
AI_GATEWAY_URL=http://10.100.60.121:8000/v1/chat/completions \
ANTHROPIC_API_KEY=<from Security secrets store> \
uvicorn app.main:app --reload --port 8080
```

Visit `http://localhost:8080/docs` for the interactive API explorer.

## Staging deployment (10.100.60.119)

Per BRD/PRD Section 18.7: one process per project, not a shared FastAPI
process. Suggested systemd unit (adjust paths/user):

```ini
[Unit]
Description=Phoneme SDLC Platform backend
After=network.target

[Service]
User=phoneme
WorkingDirectory=/opt/phoneme/projects/phoneme-sdlc-platform/src/backend
Environment=AI_GATEWAY_URL=http://10.100.60.121:8000/v1/chat/completions
Environment=ALLOWED_ORIGINS=https://phoneme-sdlc.staging.phoneme.internal
# Commercial API keys: pull from the Security service's secrets store at
# deploy time (BRD/PRD Section 18.6) — never hardcode them here or in a
# committed .env.
ExecStart=/opt/phoneme/projects/phoneme-sdlc-platform/src/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## What's real vs. stubbed in this pilot cut

- **Real**: every endpoint calls `ai_router.generate()`, which makes an
  actual HTTP request to the Ollama endpoint or the configured commercial
  provider — there is no hardcoded/mocked response path in the app itself.
- **Stubbed for the pilot**: `store.py` is in-memory (see its docstring for
  the swap-to-Postgres seam); the Astra provider in `ai_router.py` is a
  placeholder pending the provider confirmation (TDD Section 9); AAA/Gateway
  auth is not yet wired in (platform-core services aren't provisioned yet
  per TDD Section 6) — there is no login on this pilot build.
- Verified end-to-end (this session) against a local mock of the AI
  server's chat-completions endpoint, since this sandbox has no network
  path to 10.100.60.121. Re-verify against the real AI server and a real
  commercial API key once running on staging.
