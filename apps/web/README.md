# Phoneme SDLC Platform — Frontend

React + Vite port of the Idea-to-BRD/PRD Wizard mock, wired to the real
FastAPI backend (`../backend`) instead of simulated responses.

## Local run

```bash
cd src/frontend
npm install
VITE_BACKEND_URL=http://localhost:8080 npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api/*` to
`VITE_BACKEND_URL` (see `vite.config.js`) so no CORS setup is needed locally.

## Staging build

```bash
npm run build
```

Outputs static assets to `dist/`. On staging, serve `dist/` behind the API
Gateway (BRD/PRD Section 18.6) once it's provisioned; until then, serve it
from the same Staging server process as the backend (e.g. FastAPI
`StaticFiles`, or nginx) and point API calls at the backend's port directly.

## Structure

- `src/api.js` — the only place that calls `fetch()`; every stage component
  goes through it.
- `src/stages/` — one component per wizard stage (Discovery Chat, Research,
  Identity & Theme, Freeze/Generating, BRD/PRD Manager), matching the stage
  names the backend returns in `SessionState.stage`.
- `src/App.jsx` — stage router; switches on `session.stage`.

## Verified this session

Full wizard flow driven end-to-end with Playwright against the real backend
and a local mock of the AI server (no network path to 10.100.60.121 from
the build sandbox): Discovery Chat → concept summary → competitive research
+ "search more" continuation → custom name check/selection → theme pick →
module-breakdown freeze → BRD/PRD generation → Manager (comment →
regenerate → Accept & commit → Freeze). Zero console errors. Screenshots
from that run are not included here — re-run `npm run dev` alongside the
backend to see it live.
