# RelayREEL Pilot Lifecycle

Date: 2026-10-12

## Pilot Goal

RelayREEL is the proving product for GiveWings. The goal is not only to produce
RelayREEL documents; it is to expose where the GiveWings platform becomes
unclear for a real product team moving from concept note to launch.

RelayREEL concept:

Users save links, posts, videos and ideas from social platforms or the web.
RelayREEL organizes them, researches and enriches them, then helps the user
create net-new blog, carousel or short-video drafts for private use or public
publishing.

## Product Direction Captured From Research

- Stronger buyer segment: creators, marketers, curators and agencies, not
  casual consumers.
- Main legal risk: copyright/IP. RelayREEL must synthesize new content from
  ideas, facts and transcripts instead of reusing other creators' assets.
- Core differentiator: forward/save from daily browsing, then turn a grouped
  library into publishable content with review gates.
- Revenue model: freemium for limited saves, paid creator tier, pro/team tier
  for publishing and collaboration.

## RelayREEL Minimum Scope

### Standard GiveWings Modules

- Sign-in & Account
- Profile & Settings
- Admin Dashboard & Roles
- Security, Audit & Health

### Product Modules

- Capture Inbox: save links from share sheet, pasted URL, browser extension or
  bot-based forwarding.
- Library & Catalogue: group saved items by topic, source, status and readiness.
- Research & Enrichment: extract summary, facts, risks, duplicates and context.
- Create Studio: generate blog, carousel or short-video drafts from selected
  sources.
- Review & Publish: owner review, destination selection, visibility and schedule.
- Pricing & Subscription: free, creator and pro limits.

## Stage Outputs To Prove

| GiveWings stage | RelayREEL output | Quality gate |
| --- | --- | --- |
| Discovery Chat | Confirmed concept brief: target user, workflow, private/public mode, launch market, platforms | No blank core fields |
| Research | Competitor and viability report with IP/platform risks | Positioning and MVP features agreed |
| Identity | RelayREEL name, tagline, coral/ink/warm-white palette, logo and domain decision | Experience blueprint frozen |
| Freeze Scope | Standard + product modules with starts_when/outcome/access model | No module without boundary |
| Flow Design | User/system sequence for each product module | Every business module approved |
| BRD/PRD Manager | REQ-ID-backed requirements per module | Acceptance criteria complete |
| Technical Design | Stack, HLD, LLD, APIs, data model, integrations | Open questions answered/deferred |
| UI/UX Design | Screens for landing, home, share capture, library, detail, create, publish, settings | Every module has screen coverage |
| UX Flow Freeze | Journey map, states, microcopy, navigation, design tokens | Automatic gates pass |
| Ready to Build | Versioned handover pack | Pack contains all baselined docs |

## Screens Already Available

From `UI-UX/`:

- Landing page design
- Mobile concept board: home, share capture, library, content detail, create,
  review/publish
- Desktop workspace board: landing, creator home, library/catalogue, create and
  publish
- HTML landing page prototype

These should be treated as owner-provided design inputs. The GiveWings flow
should import them, split boards into screens, place them into the experience
blueprint, map business screens to modules, and explicitly ask for approval
where the AI is unsure.

## UX Gaps Found During RelayREEL

- The landing and app designs are strong, but the platform needs a clearer
  evidence trail showing how each uploaded design becomes a frozen screen.
- The platform must keep IP/copyright risk visible from Research through BRD,
  Technical Design and Review & Publish requirements.
- Private vs public publishing must remain a first-class decision, not a note
  buried in prose.
- Publishing integrations should not appear as "done" unless OAuth/API access,
  platform policies and review permissions are captured.
- Pricing exists in mockups, but sign-up and payments are not live; this should
  be marked as a launch-blocking dependency, not a visual detail.

## Build/Test/Launch Chapter Needed After Handover

Once RelayREEL reaches Ready to Build, GiveWings should create a second chapter:

1. Code Plan: epics, tickets, repo structure, implementation order.
2. AI Code Development: branch/PR generation against approved REQ-IDs.
3. Automated Validation: lint, unit tests, API tests, accessibility smoke.
4. QA/UAT: test cases generated from acceptance criteria.
5. Release Approval: human sign-off and rollback plan.
6. Production Launch: deployment record and version tag.
7. Monitoring: metrics, defects, feedback and change requests.

This chapter can initially be read-only/planned in the UI, but it must be
visible so GiveWings does not appear to stop at documentation.

## Next Platform Changes To Make With RelayREEL

1. Add a RelayREEL Product 360 view showing concept, artifacts, designs, gates
   and next action.
2. Make imported design coverage a prominent checklist before UI/UX generation.
3. Add a "launch blockers" panel that tracks unresolved dependencies such as
   payments, publishing API approvals, IP guardrails and analytics.
4. Add the future Build/Test/Launch chapter after Ready to Build.
5. Use RelayREEL as the regression product: every platform UI change should be
   checked against this pilot flow before it is considered acceptable.
