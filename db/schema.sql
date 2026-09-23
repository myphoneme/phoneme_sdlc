-- Phoneme SDLC Platform — Phase 1 (MVP) schema
-- Scope: Idea -> BRD/PRD -> REQ-ID -> Approval -> Technical Design Pack -> GitHub
-- Everything here is scoped down from the full blueprint entity list (docs/SDLC Mgmt - Blueprint.pdf,
-- section 17) to just what the BRD/PRD + Technical Design Pack stage needs. Phase 2 adds
-- services/api/db_entities/screens/test_cases/defects/releases/deployments as their own tables.

CREATE TYPE requirement_status AS ENUM (
  'draft', 'review', 'needs_clarification', 'approved', 'frozen'
);

CREATE TYPE artifact_status AS ENUM (
  'not_started', 'draft', 'approved', 'stale'
);

CREATE TYPE requirement_type AS ENUM ('functional', 'non_functional');

CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high', 'critical');

CREATE TYPE approval_decision AS ENUM ('approved', 'rejected', 'comment');

CREATE TYPE subject_kind AS ENUM ('requirement', 'artifact');

-- ---------------------------------------------------------------------------
-- Portfolio: products & modules (multi-product from day one, per blueprint
-- section 23 — Teamora HRMS is the first row in "products", not a special case)
-- ---------------------------------------------------------------------------

CREATE TABLE products (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key           TEXT UNIQUE NOT NULL,           -- e.g. 'teamora-hrms'
  name          TEXT NOT NULL,                  -- e.g. 'Teamora HRMS'
  github_repo   TEXT,                           -- e.g. 'myphoneme/hrms'
  description   TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE modules (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id    UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  key           TEXT NOT NULL,                  -- e.g. 'M1'
  name          TEXT NOT NULL,                  -- e.g. 'Recruitment'
  UNIQUE (product_id, key)
);

-- ---------------------------------------------------------------------------
-- People
-- ---------------------------------------------------------------------------

CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  email           TEXT UNIQUE NOT NULL,
  github_username TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE roles (
  id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key   TEXT UNIQUE NOT NULL   -- 'product_owner' | 'technical_reviewer' | 'security_reviewer' | 'architect' | 'admin'
);

CREATE TABLE user_roles (
  user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_id  UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  product_id UUID REFERENCES products(id) ON DELETE CASCADE,  -- NULL = global role
  PRIMARY KEY (user_id, role_id, product_id)
);

-- ---------------------------------------------------------------------------
-- Requirements — REQ-ID is the immutable spine (blueprint section 3)
-- ---------------------------------------------------------------------------

CREATE TABLE requirements (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  req_id              TEXT UNIQUE NOT NULL,      -- e.g. 'HR-M1-FR-003' — human-facing immutable key
  product_id          UUID NOT NULL REFERENCES products(id),
  module_id           UUID NOT NULL REFERENCES modules(id),
  title               TEXT NOT NULL,
  description         TEXT NOT NULL,             -- current/live text; history lives in requirement_versions
  type                requirement_type NOT NULL DEFAULT 'functional',
  priority            priority_level NOT NULL DEFAULT 'medium',
  acceptance_criteria TEXT[] NOT NULL DEFAULT '{}',
  status              requirement_status NOT NULL DEFAULT 'draft',
  current_version     INT NOT NULL DEFAULT 1,
  owner_id            UUID REFERENCES users(id),          -- Product Owner / Preparer
  approved_by         UUID REFERENCES users(id),
  approved_at         TIMESTAMPTZ,
  frozen_at           TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_requirements_product ON requirements(product_id);
CREATE INDEX idx_requirements_status  ON requirements(status);

-- Full text history per requirement. The git commit on the BRD/PRD doc in
-- GitHub remains the audit-grade record (blueprint section 9); this table is
-- the platform's fast-query index over the same history, cross-linked via
-- github_links below.
CREATE TABLE requirement_versions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  requirement_id  UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  version         INT NOT NULL,
  title           TEXT NOT NULL,
  description     TEXT NOT NULL,
  changed_by      UUID REFERENCES users(id),
  change_summary  TEXT,                          -- e.g. "Accepted AI rewrite: added transition logging + role gate"
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (requirement_id, version)
);

-- REQ-to-REQ dependency graph (blueprint section 4's traceability graph,
-- the requirement-level edge of it)
CREATE TABLE requirement_dependencies (
  requirement_id        UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  depends_on_id         UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  PRIMARY KEY (requirement_id, depends_on_id),
  CHECK (requirement_id <> depends_on_id)
);

-- ---------------------------------------------------------------------------
-- Technical Design Pack — the five (six, incl. Test Design later) standard
-- artifact types per requirement (blueprint section 6-7)
-- ---------------------------------------------------------------------------

CREATE TABLE artifact_types (
  id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key   TEXT UNIQUE NOT NULL,   -- 'tdd' | 'schema' | 'flow' | 'arch' | 'uiux' | 'test_design'
  name  TEXT NOT NULL           -- 'Technical Design Document' | 'Data Schema' | ...
);

-- One row per (requirement, artifact_type) — this is the schema-level version
-- of what the requirement-review mock calls `docsState[key]`.
CREATE TABLE artifacts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  requirement_id  UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  artifact_type_id UUID NOT NULL REFERENCES artifact_types(id),
  status          artifact_status NOT NULL DEFAULT 'not_started',
  content         TEXT,                          -- current/live content
  current_version INT NOT NULL DEFAULT 0,
  github_path     TEXT,                           -- e.g. '02-design/authentication/data-schema.md'
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (requirement_id, artifact_type_id)
);

CREATE TABLE artifact_versions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact_id     UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
  version         INT NOT NULL,
  content         TEXT NOT NULL,
  is_proposal     BOOLEAN NOT NULL DEFAULT false,
  generated_by    TEXT,                           -- 'ai' | user id as text | 'import'
  github_commit_sha TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (artifact_id, version)
);

-- ---------------------------------------------------------------------------
-- Review: comments (incl. AI-suggested rewrites) + formal approvals
-- ---------------------------------------------------------------------------

CREATE TABLE comments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_kind  subject_kind NOT NULL,
  subject_id    UUID NOT NULL,                    -- requirements.id or artifacts.id
  author_id     UUID REFERENCES users(id),         -- NULL when is_ai = true
  is_ai         BOOLEAN NOT NULL DEFAULT false,
  body          TEXT NOT NULL,
  ai_suggestion TEXT,                              -- populated only when is_ai = true
  resolved_at   TIMESTAMPTZ,                       -- set when accepted/dismissed
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_comments_subject ON comments(subject_kind, subject_id);

CREATE TABLE approvals (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_kind  subject_kind NOT NULL,
  subject_id    UUID NOT NULL,
  version       INT NOT NULL,
  approver_id   UUID NOT NULL REFERENCES users(id),
  decision      approval_decision NOT NULL,
  comment       TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_approvals_subject ON approvals(subject_kind, subject_id);

-- ---------------------------------------------------------------------------
-- Change management (blueprint section 16) — Phase 1 stub: records the
-- request + the artifacts it invalidated; the automated fan-out that
-- computes impact ships in Phase 2.
-- ---------------------------------------------------------------------------

CREATE TABLE change_requests (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  requirement_id  UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  requested_by    UUID REFERENCES users(id),
  description     TEXT NOT NULL,
  impact_summary  JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- GitHub source-of-truth links (blueprint section 9)
-- ---------------------------------------------------------------------------

CREATE TABLE github_links (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_kind  subject_kind NOT NULL,
  subject_id    UUID NOT NULL,
  repo          TEXT NOT NULL,                     -- 'myphoneme/hrms'
  path          TEXT,
  commit_sha    TEXT,
  pr_number     INT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Audit trail
-- ---------------------------------------------------------------------------

CREATE TABLE audit_events (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_kind  subject_kind NOT NULL,
  subject_id    UUID NOT NULL,
  actor_id      UUID REFERENCES users(id),
  action        TEXT NOT NULL,
  detail        JSONB,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_subject ON audit_events(subject_kind, subject_id);

-- ---------------------------------------------------------------------------
-- Seed: the five Phase-1 artifact types
-- ---------------------------------------------------------------------------

INSERT INTO artifact_types (key, name) VALUES
  ('tdd',    'Technical Design Document'),
  ('schema', 'Data Schema'),
  ('flow',   'Object / Process Flow'),
  ('arch',   'Microservices Architecture'),
  ('uiux',   'UI/UX Dataflow');
