# Phase 1 data model, state machines & BRD/PRD quality gate

Scope: Idea → BRD/PRD → REQ-ID → Approval → Technical Design Pack → GitHub,
per `docs/SDLC Mgmt - Blueprint.pdf` section 24 ("Phase 1 — MVP"). This is
the schema everything else (the web UI, the requirement-review mock, the
orchestrator) gets built against, frozen before implementation starts.

Full DDL: `db/schema.sql`.

## Entities in scope

Scoped down from the blueprint's full entity list (section 17) to what the
BRD/PRD + Technical Design Pack stage needs. Services, APIs, DB entities,
screens, test cases, defects, releases and deployments are Phase 2.

| Table | Purpose |
|---|---|
| `products`, `modules` | Multi-product portfolio from day one (Teamora HRMS is the first row, not a special case) |
| `users`, `roles`, `user_roles` | Product Owner, Technical Reviewer, Security Reviewer, Architect, Admin |
| `requirements` | The REQ-ID spine — one row per requirement, current text + status |
| `requirement_versions` | Full text history per requirement (GitHub commit stays the audit-grade record; this is the fast-query index) |
| `requirement_dependencies` | REQ-to-REQ edges |
| `artifact_types` | The 5 standard doc types (6th, Test Design, added Phase 2) |
| `artifacts` | One row per (requirement, artifact_type) — status + current content |
| `artifact_versions` | History per artifact, including AI-regenerated drafts held as proposals before acceptance |
| `comments` | Review thread per requirement or artifact, including AI-suggested rewrites |
| `approvals` | Formal sign-off records, separate from comments |
| `change_requests` | Stub for Phase 2's automated change-impact fan-out |
| `github_links` | Cross-reference to the commit/PR that is the actual source of truth |
| `audit_events` | Every state transition, approval, and AI action |

## Requirement state machine

```
DRAFT ──────► REVIEW ⇄ NEEDS_CLARIFICATION ──────► APPROVED ──────► FROZEN
```

- **DRAFT** — authored, not yet sent for review.
- **REVIEW** — a reviewer is going through it.
- **NEEDS_CLARIFICATION** — reviewer flagged a gap (a plain comment, or an
  AI-suggested rewrite sitting unresolved); loops back to REVIEW once
  resolved. This is `status: "clarify"` in the requirement-review mock.
- **APPROVED** — requirement text itself is signed off. Does **not** by
  itself mean the REQ-ID is done — see the freeze gate below.
- **FROZEN** — terminal. Requires the gate below to pass. Text is now
  immutable; any further change goes through `change_requests`, which flips
  linked artifacts to `stale` rather than editing in place.

## Artifact state machine (per requirement × doc type)

```
NOT_STARTED ──► DRAFT ──► APPROVED ──► STALE ──► (regenerate) ──► DRAFT ──► APPROVED
```

- **STALE** is only reachable from APPROVED, triggered when the parent
  requirement's text changes (an accepted AI rewrite, or a manual edit) —
  this is the cascade already prototyped in the requirement-review mock's
  "Regenerate draft" flow: stale → regenerate (simulated AI draft) → diff
  (old vs. proposed, stored as an `is_proposal = true` row in
  `artifact_versions`) → accept (commits as new version, status → DRAFT,
  needs re-review) or discard (stays STALE).

## BRD/PRD freeze gate

A requirement may transition REVIEW/NEEDS_CLARIFICATION → APPROVED → FROZEN
only when, computed live (not stored):

1. `requirements.status` would be `approved` — the text itself has a
   recorded `approvals` row with `decision = 'approved'`.
2. `acceptance_criteria` is non-empty.
3. No unresolved AI-suggested `comments` (`is_ai = true AND resolved_at IS
   NULL`) remain on the requirement.
4. Every row in `requirement_dependencies` for this requirement points to a
   requirement that exists (no dangling refs).
5. All 5 rows in `artifacts` for this requirement (one per `artifact_type`)
   are at `status = 'approved'`.

This is the same rule the requirement-review mock encodes in
`docCoverageReady()` / `freezeEligible()`, generalized from "5 hardcoded doc
keys" to "join against `artifact_types`" and from "no pending AI comment
in one array" to "no unresolved `is_ai` comment row." Nothing about the UX
validated in the mock needs to change to sit on top of this schema.

## What Phase 2 adds on top of this

Per blueprint section 24: Design → API → Database → Architecture → Code
Plan → Code Generation → PR → CI/CD, plus test generation, automated
validation, AI code review, and full requirement-to-code traceability. That
introduces `services`, `apis`, `database_entities`, `screens`, `test_cases`,
`defects`, `releases`, `deployments` — each still keyed back to `requirements`
via the same `req_id` spine.
