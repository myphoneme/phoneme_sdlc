# Discovery Log — Multi-Project Platform Standards

Source: platform review sessions, September 2026. This log captures the
decisions that fed BRD/PRD Section 18 and the standalone Technical Design
Document (PHN-PSP-2026-02-TDD), so the reasoning stays attached to the
frozen artifacts rather than living only in chat history.

## Scope decision
The Phoneme SDLC Platform is not a single-product tool: it is the standard
every Phoneme project (new and existing) is onboarded onto. This required
expanding the platform's own BRD/PRD from "how the wizard works" to "how
every project's repository, documents, and shared infrastructure work."

## Decisions reached
- Standard repo layout (`docs/`, `src/`, `.sdlc/`) — frozen, see BRD/PRD
  Section 18.1 and TDD Section 2.
- Staging server is the runtime; GitHub (`myphoneme` org) is the source of
  truth for documents and code — frozen, see TDD Section 3. Direct-commit
  vs. branch+PR for regeneration is still open.
- Two onboarding paths (New Project wizard vs. Existing Project scan) are
  distinct capabilities, not a wizard variant — see BRD/PRD Section 18.3.
- Change management generalizes the existing Regenerate-from-Comments
  mechanic, triggered by a Change Request instead of a reviewer comment —
  see BRD/PRD Section 18.4.
- A global Skills repository (`phoneme-sdlc-skills`) holds every AI Skill
  as reusable template + logic, versioned independently of any project —
  see BRD/PRD Section 18.5.
- Platform-core shared services — AAA, Security, API Gateway — are built
  once and consumed by every project rather than rebuilt per project.
  AAA and API Gateway get dedicated instances; general shared code follows
  a shared-library-per-project-deploy model — see BRD/PRD Section 18.6 and
  TDD Section 5.
- Infra allocation across the three existing instances (DB, Staging, AI)
  plus two new instances (AAA, API Gateway) — see TDD Section 6.
- AI model routing policy: commercial models (Sonnet/Gemini/Astra*) for
  critical, accuracy-sensitive generation; local Ollama for non-critical
  NLU. Captured in the TDD *before* implementation, per explicit
  instruction — see TDD Section 8.
- The AI server's existing endpoint (port 8000, OpenAI-compatible,
  `gemma4:e4b`) was validated live and appears to already sit behind a
  search-capable wrapper, not bare Ollama — see TDD Section 8.1.

## Open items
Tracked in TDD Section 9 (PHN-PSP-2026-02-TDD) — not duplicated here to
avoid drift between this log and the frozen document.
