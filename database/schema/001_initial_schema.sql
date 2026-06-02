-- =============================================================================
-- Celerius Clinical Trial Lifecycle Platform
-- Initial Database Schema
-- =============================================================================
-- All tables follow these conventions:
--   - UUID primary keys (gen_random_uuid())
--   - created_at / updated_at timestamps (WITH TIME ZONE)
--   - organization_id on every tenant-scoped table
--   - deleted_at for soft deletes (NULL = active)
--   - Append-only tables (audit_logs, artifact_versions) have no updated_at
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE user_role AS ENUM ('ADMIN', 'CONTRIBUTOR', 'REVIEWER');

CREATE TYPE artifact_status AS ENUM (
    'DRAFT',
    'IN_REVIEW',
    'APPROVED',
    'REJECTED',
    'LOCKED',
    'AMENDED',
    'SUPERSEDED'
);

CREATE TYPE artifact_type AS ENUM (
    'PROTOCOL',
    'ICF',
    'SAP',
    'EDC_CRF',
    'TRACEABILITY_MATRIX',
    'SDTM_DATASET',
    'ADAM_DATASET',
    'TLF',
    'VALIDATION_REPORT',
    'CSR',
    'SUBMISSION_PACKAGE',
    'OTHER'
);

CREATE TYPE study_phase AS ENUM (
    'PHASE_1',
    'PHASE_1_2',
    'PHASE_2',
    'PHASE_2_3',
    'PHASE_3',
    'PHASE_3_4',
    'PHASE_4',
    'OBSERVATIONAL',
    'OTHER'
);

CREATE TYPE study_status AS ENUM (
    'DRAFT',
    'ACTIVE',
    'ON_HOLD',
    'COMPLETED',
    'ARCHIVED',
    'TERMINATED'
);

CREATE TYPE approval_decision AS ENUM ('APPROVED', 'REJECTED');

CREATE TYPE audit_action AS ENUM (
    -- Auth
    'user.login', 'user.logout', 'user.login_failed', 'user.token_refreshed',
    -- User management
    'user.created', 'user.updated', 'user.deactivated', 'user.role_changed', 'user.password_changed',
    -- Organization
    'org.created', 'org.settings_changed', 'org.member_added', 'org.member_removed',
    -- Study
    'study.created', 'study.updated', 'study.archived',
    'study.member_added', 'study.member_removed', 'study.member_role_changed',
    -- Artifact
    'artifact.created', 'artifact.updated', 'artifact.submitted',
    'artifact.approved', 'artifact.rejected', 'artifact.locked',
    'artifact.amended', 'artifact.superseded', 'artifact.deleted',
    -- Versions
    'artifact_version.created',
    -- Comments
    'comment.created', 'comment.updated', 'comment.deleted', 'comment.resolved',
    -- Validation
    'validation.run_started', 'validation.run_completed', 'validation.run_failed',
    -- AI
    'ai.generation_started', 'ai.generation_completed', 'ai.generation_failed',
    -- Data
    'data.file_uploaded', 'data.file_deleted',
    -- Submission
    'submission.package_created', 'submission.package_exported'
);

CREATE TYPE validation_status AS ENUM ('PENDING', 'RUNNING', 'PASSED', 'FAILED', 'ERROR');

CREATE TYPE notification_type AS ENUM (
    'ARTIFACT_SUBMITTED', 'ARTIFACT_APPROVED', 'ARTIFACT_REJECTED',
    'ARTIFACT_LOCKED', 'COMMENT_ADDED', 'MENTION', 'VALIDATION_COMPLETE'
);

CREATE TYPE generation_job_status AS ENUM (
    'PENDING', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'
);

-- =============================================================================
-- ORGANIZATIONS
-- =============================================================================

CREATE TABLE organizations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,
    slug                VARCHAR(100) NOT NULL UNIQUE,
    description         TEXT,
    logo_url            VARCHAR(500),
    settings            JSONB NOT NULL DEFAULT '{}',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_active ON organizations(is_active) WHERE deleted_at IS NULL;

COMMENT ON TABLE organizations IS 'Top-level tenant entity. Each organization is fully isolated from others.';

-- =============================================================================
-- USERS
-- =============================================================================

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email               VARCHAR(255) NOT NULL,
    email_verified      BOOLEAN NOT NULL DEFAULT FALSE,
    hashed_password     VARCHAR(255) NOT NULL,
    full_name           VARCHAR(255) NOT NULL,
    title               VARCHAR(100),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    is_system_admin     BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at       TIMESTAMP WITH TIME ZONE,
    failed_login_count  INTEGER NOT NULL DEFAULT 0,
    locked_until        TIMESTAMP WITH TIME ZONE,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMP WITH TIME ZONE,

    CONSTRAINT uq_users_org_email UNIQUE (organization_id, email)
);

CREATE INDEX idx_users_org ON users(organization_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_org_active ON users(organization_id, is_active) WHERE deleted_at IS NULL;

COMMENT ON TABLE users IS 'Platform users. Email is unique per organization. Passwords stored as bcrypt hashes.';
COMMENT ON COLUMN users.is_system_admin IS 'Cross-organization admin access. Not the same as org-level Admin role.';

-- =============================================================================
-- REFRESH TOKENS
-- =============================================================================

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL UNIQUE,
    expires_at      TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at      TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address      INET,
    user_agent      TEXT
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id) WHERE NOT is_revoked;
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);

COMMENT ON TABLE refresh_tokens IS 'Stored refresh tokens for JWT rotation. One-time use; rotated on each refresh.';

-- =============================================================================
-- STUDIES
-- =============================================================================

CREATE TABLE studies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    protocol_number     VARCHAR(100) NOT NULL,
    name                VARCHAR(500) NOT NULL,
    short_name          VARCHAR(100),
    description         TEXT,
    indication          VARCHAR(500),
    therapeutic_area    VARCHAR(255),
    phase               study_phase,
    status              study_status NOT NULL DEFAULT 'DRAFT',
    sponsor             VARCHAR(255),
    regulatory_region   VARCHAR(100)[], -- e.g., ['US', 'EU', 'JP']
    start_date          DATE,
    end_date            DATE,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_by_id       UUID NOT NULL REFERENCES users(id),
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMP WITH TIME ZONE,

    CONSTRAINT uq_studies_org_protocol UNIQUE (organization_id, protocol_number)
);

CREATE INDEX idx_studies_org ON studies(organization_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_studies_org_status ON studies(organization_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_studies_protocol ON studies(protocol_number);

COMMENT ON TABLE studies IS 'Clinical trial study. Container for all artifacts and members. Protocol number is unique per organization.';

-- =============================================================================
-- STUDY MEMBERS (Role Assignments)
-- =============================================================================

CREATE TABLE study_members (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_id        UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role            user_role NOT NULL,
    invited_by_id   UUID REFERENCES users(id),
    joined_at       TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_study_members UNIQUE (study_id, user_id)
);

CREATE INDEX idx_study_members_study ON study_members(study_id);
CREATE INDEX idx_study_members_user ON study_members(user_id);
CREATE INDEX idx_study_members_org ON study_members(organization_id);

COMMENT ON TABLE study_members IS 'Study-level role assignments. A user can have different roles on different studies.';

-- =============================================================================
-- ARTIFACTS
-- =============================================================================

CREATE TABLE artifacts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    study_id                UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    artifact_type           artifact_type NOT NULL,
    name                    VARCHAR(500) NOT NULL,
    description             TEXT,
    status                  artifact_status NOT NULL DEFAULT 'DRAFT',
    current_version_id      UUID, -- FK set after first version created (circular, deferred)
    current_version_number  INTEGER NOT NULL DEFAULT 0,
    locked_at               TIMESTAMP WITH TIME ZONE,
    locked_by_id            UUID REFERENCES users(id),
    amendment_of_id         UUID REFERENCES artifacts(id), -- points to LOCKED artifact this amends
    superseded_by_id        UUID REFERENCES artifacts(id), -- set when a newer version supersedes this
    tags                    VARCHAR(100)[],
    metadata                JSONB NOT NULL DEFAULT '{}',
    created_by_id           UUID NOT NULL REFERENCES users(id),
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_artifacts_org ON artifacts(organization_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifacts_study ON artifacts(study_id, artifact_type) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifacts_org_status ON artifacts(organization_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_artifacts_org_type ON artifacts(organization_id, artifact_type) WHERE deleted_at IS NULL;

COMMENT ON TABLE artifacts IS 'Core content objects. Protocol, ICF, SAP, SDTM datasets, etc. All version history preserved in artifact_versions.';
COMMENT ON COLUMN artifacts.current_version_id IS 'FK to the latest artifact_versions record. Updated on each version creation.';
COMMENT ON COLUMN artifacts.amendment_of_id IS 'If this is an amendment, points to the LOCKED artifact it amends. The LOCKED artifact status changes to AMENDED.';

-- =============================================================================
-- ARTIFACT VERSIONS (Append-Only)
-- =============================================================================

CREATE TABLE artifact_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id     UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,
    content         JSONB NOT NULL DEFAULT '{}',  -- full content snapshot
    content_hash    VARCHAR(64) NOT NULL,           -- SHA-256 of content for integrity
    content_diff    JSONB,                          -- JSON Patch (RFC 6902) vs. previous version
    file_path       VARCHAR(1000),                  -- storage path for binary content
    file_size_bytes BIGINT,
    file_mime_type  VARCHAR(100),
    change_summary  TEXT,
    status_at_creation artifact_status NOT NULL,
    created_by_id   UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    -- NO updated_at: this table is append-only

    CONSTRAINT uq_artifact_versions UNIQUE (artifact_id, version_number),
    CONSTRAINT chk_version_positive CHECK (version_number > 0)
);

CREATE INDEX idx_artifact_versions_artifact ON artifact_versions(artifact_id, version_number DESC);
CREATE INDEX idx_artifact_versions_org ON artifact_versions(organization_id, created_at DESC);
CREATE INDEX idx_artifact_versions_current ON artifact_versions(artifact_id) WHERE is_current = TRUE;

COMMENT ON TABLE artifact_versions IS 'Append-only version history for all artifacts. No UPDATE or DELETE permitted. Every content change creates a new row.';
COMMENT ON COLUMN artifact_versions.content_hash IS 'SHA-256 of JSON-serialized content. Used for integrity verification and deduplication.';
COMMENT ON COLUMN artifact_versions.content_diff IS 'JSON Patch (RFC 6902) representing the delta from the previous version. NULL for version 1.';

-- =============================================================================
-- COMMENTS
-- =============================================================================

CREATE TABLE comments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    artifact_id     UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    artifact_version_id UUID REFERENCES artifact_versions(id),
    parent_id       UUID REFERENCES comments(id), -- for threaded replies
    author_id       UUID NOT NULL REFERENCES users(id),
    body            TEXT NOT NULL,
    is_resolved     BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMP WITH TIME ZONE,
    resolved_by_id  UUID REFERENCES users(id),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_comments_artifact ON comments(artifact_id, created_at DESC) WHERE NOT is_deleted;
CREATE INDEX idx_comments_org ON comments(organization_id, created_at DESC) WHERE NOT is_deleted;

COMMENT ON TABLE comments IS 'Review comments on artifacts. Supports threads via parent_id. Resolved comments are preserved for regulatory history.';

-- =============================================================================
-- APPROVALS
-- =============================================================================

CREATE TABLE approvals (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    artifact_id             UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    artifact_version_id     UUID NOT NULL REFERENCES artifact_versions(id),
    approver_id             UUID NOT NULL REFERENCES users(id),
    decision                approval_decision NOT NULL,
    comments                TEXT,
    electronic_signature    JSONB, -- name, date, meaning (21 CFR Part 11)
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    -- NO updated_at: immutable once created
);

CREATE INDEX idx_approvals_artifact ON approvals(artifact_id, created_at DESC);
CREATE INDEX idx_approvals_org ON approvals(organization_id, created_at DESC);

COMMENT ON TABLE approvals IS 'Append-only approval chain. Each approve/reject action creates one record. Immutable once created.';
COMMENT ON COLUMN approvals.electronic_signature IS 'JSON capture of electronic signature per 21 CFR Part 11: full name, date/time, role, and meaning of signature.';

-- =============================================================================
-- AUDIT LOGS (Append-Only)
-- =============================================================================

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id), -- nullable for system-level events
    actor_user_id   UUID REFERENCES users(id),         -- nullable for system events
    action          audit_action NOT NULL,
    resource_type   VARCHAR(100) NOT NULL,
    resource_id     UUID,
    before_state    JSONB,
    after_state     JSONB,
    metadata        JSONB NOT NULL DEFAULT '{}',
    ip_address      INET,
    user_agent      TEXT,
    session_id      VARCHAR(255),
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    -- NO updated_at: this table is append-only
);

CREATE INDEX idx_audit_logs_org ON audit_logs(organization_id, created_at DESC);
CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_user_id, created_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action, created_at DESC);
CREATE INDEX idx_audit_logs_org_action ON audit_logs(organization_id, action, created_at DESC);

COMMENT ON TABLE audit_logs IS 'Immutable audit trail. Append-only. No UPDATE or DELETE permitted. 15-year minimum retention.';

-- Trigger to prevent UPDATE and DELETE on audit_logs
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs records are immutable and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_logs_no_update
    BEFORE UPDATE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

CREATE TRIGGER trg_audit_logs_no_delete
    BEFORE DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

-- Trigger to prevent UPDATE and DELETE on artifact_versions
CREATE OR REPLACE FUNCTION prevent_version_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'artifact_versions records are immutable and cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_artifact_versions_no_update
    BEFORE UPDATE ON artifact_versions
    FOR EACH ROW EXECUTE FUNCTION prevent_version_modification();

CREATE TRIGGER trg_artifact_versions_no_delete
    BEFORE DELETE ON artifact_versions
    FOR EACH ROW EXECUTE FUNCTION prevent_version_modification();

-- =============================================================================
-- VALIDATION RUNS
-- =============================================================================

CREATE TABLE validation_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    artifact_id         UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    artifact_version_id UUID NOT NULL REFERENCES artifact_versions(id),
    engine              VARCHAR(100) NOT NULL DEFAULT 'internal',  -- 'internal', 'pinnacle21', etc.
    status              validation_status NOT NULL DEFAULT 'PENDING',
    rule_set_version    VARCHAR(50),
    total_checks        INTEGER,
    passed_checks       INTEGER,
    failed_checks       INTEGER,
    warnings            INTEGER,
    results             JSONB,
    report_path         VARCHAR(1000), -- storage path to full report
    started_at          TIMESTAMP WITH TIME ZONE,
    completed_at        TIMESTAMP WITH TIME ZONE,
    triggered_by_id     UUID NOT NULL REFERENCES users(id),
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_validation_runs_artifact ON validation_runs(artifact_id, created_at DESC);
CREATE INDEX idx_validation_runs_org ON validation_runs(organization_id, created_at DESC);

COMMENT ON TABLE validation_runs IS 'Validation job records for Pinnacle 21 and internal CDISC validation. Results preserved as regulatory evidence.';

-- =============================================================================
-- TRACEABILITY MATRIX
-- =============================================================================

CREATE TABLE traceability_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    study_id            UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    source_artifact_id  UUID NOT NULL REFERENCES artifacts(id),
    source_element_ref  VARCHAR(500), -- e.g., "Section 3.1.2", "Endpoint EP-001"
    target_artifact_id  UUID NOT NULL REFERENCES artifacts(id),
    target_element_ref  VARCHAR(500), -- e.g., "ADLB.VISITNUM", "Table 14.1.1"
    link_type           VARCHAR(100) NOT NULL, -- 'derives_from', 'implements', 'validates', etc.
    description         TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_by_id       UUID NOT NULL REFERENCES users(id),
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_traceability_study ON traceability_links(study_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_traceability_source ON traceability_links(source_artifact_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_traceability_target ON traceability_links(target_artifact_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_traceability_org ON traceability_links(organization_id) WHERE deleted_at IS NULL;

COMMENT ON TABLE traceability_links IS 'Objective → Endpoint → eCRF → SDTM → ADaM → TLF → CSR traceability chain. Every link is versioned and auditable.';

-- =============================================================================
-- NOTIFICATIONS
-- =============================================================================

CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    recipient_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            notification_type NOT NULL,
    title           VARCHAR(500) NOT NULL,
    body            TEXT NOT NULL,
    resource_type   VARCHAR(100),
    resource_id     UUID,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    read_at         TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_recipient ON notifications(recipient_id, created_at DESC) WHERE NOT is_read;
CREATE INDEX idx_notifications_org ON notifications(organization_id, created_at DESC);

COMMENT ON TABLE notifications IS 'In-platform notifications. Does not replace audit logs — notifications are user-facing convenience, not regulatory records.';

-- =============================================================================
-- AI GENERATION JOBS
-- =============================================================================

CREATE TABLE generation_jobs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    study_id                UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    artifact_type           artifact_type NOT NULL,
    status                  generation_job_status NOT NULL DEFAULT 'PENDING',
    model_id                VARCHAR(100) NOT NULL,
    model_version           VARCHAR(50),
    prompt_template_id      VARCHAR(100),
    prompt_template_hash    VARCHAR(64),
    input_context           JSONB NOT NULL DEFAULT '{}',
    input_context_hash      VARCHAR(64),
    output_artifact_id      UUID REFERENCES artifacts(id),
    error_message           TEXT,
    started_at              TIMESTAMP WITH TIME ZONE,
    completed_at            TIMESTAMP WITH TIME ZONE,
    triggered_by_id         UUID NOT NULL REFERENCES users(id),
    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_generation_jobs_org ON generation_jobs(organization_id, created_at DESC);
CREATE INDEX idx_generation_jobs_study ON generation_jobs(study_id, created_at DESC);
CREATE INDEX idx_generation_jobs_status ON generation_jobs(status, created_at DESC);

COMMENT ON TABLE generation_jobs IS 'AI generation job tracking. All generation inputs logged for reproducibility. Output is always a DRAFT artifact.';

-- =============================================================================
-- DEFERRED FOREIGN KEY: artifacts.current_version_id
-- =============================================================================

ALTER TABLE artifacts
    ADD CONSTRAINT fk_artifacts_current_version
    FOREIGN KEY (current_version_id) REFERENCES artifact_versions(id)
    DEFERRABLE INITIALLY DEFERRED;

-- =============================================================================
-- UPDATED_AT TRIGGER (applied to all tables with updated_at)
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'organizations', 'users', 'studies', 'study_members', 'artifacts',
        'comments', 'traceability_links', 'generation_jobs'
    ] LOOP
        EXECUTE format('
            CREATE TRIGGER trg_%s_updated_at
            BEFORE UPDATE ON %s
            FOR EACH ROW EXECUTE FUNCTION update_updated_at()',
            t, t
        );
    END LOOP;
END;
$$;

-- =============================================================================
-- SCHEMA VERSION RECORD
-- =============================================================================

CREATE TABLE schema_versions (
    id          SERIAL PRIMARY KEY,
    version     VARCHAR(50) NOT NULL,
    description TEXT,
    applied_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

INSERT INTO schema_versions (version, description)
VALUES ('001', 'Initial schema: organizations, users, studies, artifacts, versioning, audit, traceability');
