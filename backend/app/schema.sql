-- Kaagaz schema. Idempotent: applied on every API/worker start.
-- Every tenant-owned row carries org_id; the API filters on it in every query.

CREATE TABLE IF NOT EXISTS orgs (
  id          BIGSERIAL PRIMARY KEY,
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
  id             BIGSERIAL PRIMARY KEY,
  org_id         BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  email          TEXT NOT NULL,
  name           TEXT NOT NULL,
  password_hash  TEXT NOT NULL,
  role           TEXT NOT NULL CHECK (role IN ('admin', 'reviewer')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_uq ON users (lower(email));

-- One claim = one verification job. state tracks the job, status is the outcome.
CREATE TABLE IF NOT EXISTS claims (
  id             BIGSERIAL PRIMARY KEY,
  org_id         BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  created_by     BIGINT REFERENCES users(id) ON DELETE SET NULL,
  claim_ref      TEXT,
  state          TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'processing', 'done', 'failed')),
  status         TEXT CHECK (status IN ('consistent', 'needs_review', 'incomplete')),
  error          TEXT,
  patient_name   TEXT,
  hospital_name  TEXT,
  total_claimed  NUMERIC(14, 2),
  attempts       INT NOT NULL DEFAULT 0,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at     TIMESTAMPTZ,
  finished_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS claims_org_created ON claims (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS claims_org_ref ON claims (org_id, claim_ref);
CREATE INDEX IF NOT EXISTS claims_queue ON claims (created_at) WHERE state = 'queued';

CREATE TABLE IF NOT EXISTS documents (
  id                 BIGSERIAL PRIMARY KEY,
  org_id             BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  claim_id           BIGINT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  filename           TEXT NOT NULL,
  sha256             TEXT NOT NULL,
  size_bytes         INT NOT NULL,
  pages              INT,
  file_enc           BYTEA,          -- Fernet-encrypted PDF; NULL once purged by retention
  doc_type           TEXT,
  extraction_method  TEXT,
  data               JSONB,          -- extracted fields (ParsedDocument)
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (claim_id, sha256)
);
CREATE INDEX IF NOT EXISTS documents_claim ON documents (claim_id);
CREATE INDEX IF NOT EXISTS documents_org_sha ON documents (org_id, sha256);
CREATE INDEX IF NOT EXISTS documents_org_invoice ON documents (org_id, (data->>'invoice_number')) WHERE doc_type = 'invoice';

CREATE TABLE IF NOT EXISTS findings (
  id               BIGSERIAL PRIMARY KEY,
  org_id           BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  claim_id         BIGINT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  code             TEXT NOT NULL,
  severity         TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'action_required', 'policy_review')),
  title            TEXT NOT NULL,
  detail           TEXT NOT NULL,
  extracted_value  TEXT,
  expected_value   TEXT,
  document_ref     TEXT,
  policy_clause    TEXT,
  confidence       REAL NOT NULL,
  action           TEXT,
  UNIQUE (claim_id, code)
);

-- Append-only: the latest row per finding is the current decision, older rows are history.
CREATE TABLE IF NOT EXISTS reviews (
  id           BIGSERIAL PRIMARY KEY,
  org_id       BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  finding_id   BIGINT NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
  reviewer_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
  decision     TEXT NOT NULL CHECK (decision IN ('confirmed', 'dismissed', 'inconclusive')),
  comment      TEXT NOT NULL DEFAULT '',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS reviews_finding ON reviews (finding_id, created_at DESC);

-- Who touched which claim (health data): views, downloads, reviews, deletions.
CREATE TABLE IF NOT EXISTS access_log (
  id          BIGSERIAL PRIMARY KEY,
  org_id      BIGINT NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  user_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
  action      TEXT NOT NULL,
  claim_id    BIGINT,          -- no FK: entries must outlive deleted claims
  detail      TEXT,
  ip          TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS access_log_org_created ON access_log (org_id, created_at DESC);

-- Supabase exposes the public schema over its REST API. RLS with no policies
-- denies anon/authenticated roles entirely; the API connects as the table owner
-- (bypasses RLS) and scopes by org_id itself.
ALTER TABLE orgs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE users      ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims     ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents  ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings   ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews    ENABLE ROW LEVEL SECURITY;
ALTER TABLE access_log ENABLE ROW LEVEL SECURITY;
