# GiveWings Platform UX Gap Analysis

Date: 2026-10-12

## North Star

GiveWings should not feel like a generic AI document generator. It should feel
like a product launch control plane for mixed teams: marketing people can enter
and refine ideas safely, while technical reviewers see the decisions, gates,
traceability and launch readiness needed to turn those ideas into commercial
SaaS products.

The frozen stage model in the current app is a good foundation:

1. Discovery Chat
2. Research
3. Identity
4. Freeze Scope
5. Flow Design
6. Drafting BRD/PRD
7. BRD/PRD Manager
8. Technical Design
9. UI/UX Design
10. UX Flow Freeze
11. Ready to Build

The product vision in the BRD/PRD and blueprint is broader:

Idea -> Requirements -> Architecture -> Design -> Code -> Test -> Release ->
Production -> Monitoring -> Change Request.

The UI challenge is therefore not changing the frozen early stages. It is
showing users that those stages are the first controlled chapter of a complete
launch lifecycle.

## What Is Working

- The app already preserves a clear journey rail and lets users look back at
  completed stages without losing the current stage.
- The Concept Brief prevents the RelayREEL problem found in the dry run, where
  important decisions such as private/public mode, market and platform were
  silently assumed.
- Identity now includes name, domain, tagline, theme, logo, experience
  blueprint and imported owner designs.
- Scope Freeze is no longer only a list of modules. It captures boundaries:
  starts when, outcome, access mode and product-specific tailoring.
- Flow Design correctly sits before BRD/PRD drafting, reducing abstract
  requirements that an AI coding agent cannot build from.
- Review stages use a consistent loop: comment, revised draft, accept/discard,
  approve, freeze, baseline.
- UX Flow Freeze has automatic gates for journeys, states, navigation and
  traceability before the handover pack opens.

## Main UX Gaps

### 1. The Dashboard Feels Like A Marketing Workspace

The first screen says "Turn bold ideas into real products," but it does not yet
show the SDLC operating model. A product owner should immediately see:

- Which ideas are blocked, which are waiting for review and which are ready for
  the next gate.
- Which artifact set is the source of truth for each product.
- Which lifecycle phase each product is in beyond document readiness.
- Which reviewer or owner has the next action.

Recommended direction: replace the hero-led dashboard with a lifecycle cockpit:
portfolio status, stage distribution, blocked gates, next owner actions and a
RelayREEL pilot lane.

### 2. Stage Progress Is Linear, But The Mental Model Is Governed Gates

The journey rail communicates sequence well, but non-technical users need to
understand what they must decide at each step and what becomes frozen after it.

Recommended direction: every stage header should show:

- Decision required from user.
- Generated artifact.
- Freeze condition.
- Downstream impact if changed later.

This can be displayed as compact metadata rather than explanatory paragraphs.

### 3. "Ready To Build" Sounds Like The End

The current final screen correctly produces the build-team handover pack, but
the platform vision continues into code, QA, release and production.

Recommended direction: keep "Ready to Build" as the end of the documentation
stage, then show a disabled/future "Build & Launch" chapter:

- Code Plan
- AI Code Development
- Pull Request
- Automated Validation
- QA/UAT
- Release Approval
- Production
- Monitoring
- Change Request

This avoids disturbing frozen stages while aligning the product with the full
concept-to-launch promise.

### 4. RelayREEL Designs Are Strong, But Need To Become Platform Evidence

RelayREEL has good visual direction: coral/ink/warm-white palette, clear
mobile flows, share capture, library, create and publish screens, plus desktop
workspace concepts.

The GiveWings UI should treat these not as loose mockups, but as inputs and
evidence:

- Which uploaded screens were recognized?
- Which frame slots were filled?
- Which modules did each screen map to?
- Which missing screens will GiveWings generate?
- Which screens are owner-approved vs AI-generated?

The code already models much of this under `DesignAsset`, `DesignHints` and
design coverage. The UX should make it highly visible.

### 5. Business Users Need Fewer Technical Words, Technical Users Need More Traceability

A mixed marketing/technical team needs two lenses over the same data:

- Business lens: idea, audience, market, offer, screens, pricing, launch risk.
- Engineering lens: REQ-ID, APIs, data model, services, tests, releases.

Recommended direction: add a role-aware toggle or tabs inside review screens:
Business View, Technical View and Trace View. The underlying source stays the
same; only presentation changes.

## Target Product Experience

### Portfolio Cockpit

Purpose: answer "what needs attention today?"

Suggested blocks:

- Stage distribution: Discovery, Requirements, Design, Build, Test, Launch.
- Blocked gates: open questions, missing designs, unapproved docs, failed tests.
- Products table: product, stage, owner, next action, artifact version, launch
  target.
- Pilot lane: RelayREEL as the reference product proving the full system.

### Product 360

Purpose: one screen per product that combines status, artifacts and traceability.

Suggested blocks:

- Product brief: name, tagline, market, audience, platform, business model.
- Lifecycle map: current stage, completed stages, next gate.
- Artifact stack: BRD/PRD, Technical Design, UI/UX, UX Flow, Code Plan, Test
  Plan, Release Plan.
- Requirement traceability: REQ-ID -> module -> screen -> API -> test -> PR.
- Decisions and risks: deferred questions, assumptions, compliance/IP risks.

### Stage Workspace

Purpose: let users finish one stage without losing context.

Each stage should consistently expose:

- Inputs used by AI.
- Draft artifact.
- Owner decisions.
- Reviewer comments.
- Freeze gate.
- Downloads and baseline version.

## Bare Minimum Quality Standard

Every commercial product generated through GiveWings should have these minimum
checks before launch:

- Confirmed concept brief with no hidden assumptions.
- Research report with competitors, positioning, risks and monetization.
- Frozen identity and experience blueprint.
- Frozen module scope with clear boundaries and access model.
- Approved module flows before requirements are drafted.
- BRD/PRD with acceptance criteria for every module.
- Technical design with stack, HLD, LLD, APIs and data model.
- UI/UX design with every required screen and screen state.
- UX flow specification with journey gates passed.
- Handover pack versioned and downloadable.
- Build chapter created with code plan, QA plan, release gate and change
  management path.

## Immediate Build Priorities

1. Convert the dashboard from a hero page into a lifecycle cockpit.
2. Add a Product 360 page for RelayREEL using existing session/artifact data.
3. Extend "Ready to Build" with a visible future chapter for Build/Test/Launch.
4. Make design import coverage prominent in Identity and UI/UX stages.
5. Add stage-level "decision, artifact, gate, downstream impact" metadata.
6. Use RelayREEL as the golden-path demo product and keep fixing the platform
   wherever that cycle feels unclear.
