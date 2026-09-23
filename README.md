# Phoneme SDLC Platform

AI-assisted SDLC operating system for Phoneme's SaaS products. One web
platform that takes a product from Idea → Requirements → Architecture →
Design → Code → Test → Release → Production, with REQ-ID as the immutable
spine of the entire lifecycle and full traceability across every artifact.

This is the platform itself — it manages products (Teamora HRMS being the
first), it is not a product's own repo. See `docs/SDLC Mgmt - Blueprint.pdf`
for the founding architecture document.

## Layout

- `docs/` — the platform's own BRD/PRD and founding architecture docs
- `apps/web/` — the web interface (control plane)
- `apps/orchestrator/` — workflow engine, state machine, quality gates, AI
  skill router, GitHub integration
- `db/` — schema + migrations

## Status

Phase 0 — repo scaffolded, backend data model and state machine being
drafted against `docs/SDLC Mgmt - Blueprint.pdf` before implementation
begins.
