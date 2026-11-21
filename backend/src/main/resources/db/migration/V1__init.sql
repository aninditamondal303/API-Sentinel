-- API Sentinel backend schema, version 1.
-- Specification content lives in its own table so listing versions never loads documents,
-- and scans reference specifications instead of copying them.

CREATE TABLE users (
    id            UUID PRIMARY KEY,
    email         VARCHAR(254) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    display_name  VARCHAR(100) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL
);
CREATE UNIQUE INDEX ux_users_email ON users (LOWER(email));

CREATE TABLE projects (
    id                    UUID PRIMARY KEY,
    owner_id              UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name                  VARCHAR(100) NOT NULL,
    description           VARCHAR(1000),
    -- Compatibility policy (embedded): default threshold for new scans; NULL disables it.
    policy_fail_on        VARCHAR(16),
    policy_fail_on_manual_review BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ  NOT NULL,
    updated_at            TIMESTAMPTZ  NOT NULL
);
CREATE UNIQUE INDEX ux_projects_owner_name ON projects (owner_id, LOWER(name));

CREATE TABLE api_specifications (
    id                UUID PRIMARY KEY,
    project_id        UUID         NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    version_label     VARCHAR(50)  NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    source_format     VARCHAR(8)   NOT NULL,
    openapi_version   VARCHAR(16)  NOT NULL,
    title             VARCHAR(255),
    api_version       VARCHAR(100),
    operation_count   INTEGER      NOT NULL,
    size_bytes        INTEGER      NOT NULL,
    sha256            VARCHAR(64)  NOT NULL,
    uploaded_by       UUID         NOT NULL REFERENCES users (id),
    created_at        TIMESTAMPTZ  NOT NULL
);
CREATE UNIQUE INDEX ux_specs_project_label ON api_specifications (project_id, LOWER(version_label));
CREATE UNIQUE INDEX ux_specs_project_sha ON api_specifications (project_id, sha256);
CREATE INDEX ix_specs_project_created ON api_specifications (project_id, created_at DESC);

CREATE TABLE specification_contents (
    specification_id UUID PRIMARY KEY REFERENCES api_specifications (id) ON DELETE CASCADE,
    content          TEXT NOT NULL
);

CREATE TABLE scans (
    id                       UUID PRIMARY KEY,
    project_id               UUID        NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    scan_type                VARCHAR(16) NOT NULL,
    status                   VARCHAR(16) NOT NULL,
    baseline_specification_id UUID REFERENCES api_specifications (id),
    target_specification_id   UUID NOT NULL REFERENCES api_specifications (id),
    fail_on                  VARCHAR(16),
    fail_on_manual_review    BOOLEAN     NOT NULL,
    decision                 VARCHAR(8),
    decision_reasons         TEXT,
    total_findings           INTEGER     NOT NULL DEFAULT 0,
    critical_count           INTEGER     NOT NULL DEFAULT 0,
    high_count               INTEGER     NOT NULL DEFAULT 0,
    medium_count             INTEGER     NOT NULL DEFAULT 0,
    low_count                INTEGER     NOT NULL DEFAULT 0,
    info_count               INTEGER     NOT NULL DEFAULT 0,
    breaking_changes         INTEGER     NOT NULL DEFAULT 0,
    manual_review_count      INTEGER     NOT NULL DEFAULT 0,
    endpoints_affected       INTEGER     NOT NULL DEFAULT 0,
    analyzer_version         VARCHAR(32),
    ruleset_version          VARCHAR(32),
    error_code               VARCHAR(64),
    error_message            VARCHAR(500),
    duration_ms              BIGINT,
    created_by               UUID        NOT NULL REFERENCES users (id),
    created_at               TIMESTAMPTZ NOT NULL,
    completed_at             TIMESTAMPTZ,
    CONSTRAINT ck_scans_type CHECK (scan_type IN ('COMPATIBILITY', 'SECURITY')),
    CONSTRAINT ck_scans_status CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    CONSTRAINT ck_scans_baseline CHECK (
        (scan_type = 'COMPATIBILITY' AND baseline_specification_id IS NOT NULL
             AND baseline_specification_id <> target_specification_id)
        OR (scan_type = 'SECURITY' AND baseline_specification_id IS NULL))
);
CREATE INDEX ix_scans_project_created ON scans (project_id, created_at DESC);

CREATE TABLE findings (
    id                     UUID PRIMARY KEY,
    scan_id                UUID         NOT NULL REFERENCES scans (id) ON DELETE CASCADE,
    position               INTEGER      NOT NULL,
    rule_id                VARCHAR(32)  NOT NULL,
    title                  VARCHAR(200) NOT NULL,
    category               VARCHAR(32)  NOT NULL,
    severity               VARCHAR(16)  NOT NULL,
    requires_manual_review BOOLEAN      NOT NULL,
    http_method            VARCHAR(16),
    path                   VARCHAR(1000),
    location               VARCHAR(2000) NOT NULL,
    location_document      VARCHAR(16)  NOT NULL,
    field_path             VARCHAR(1000),
    old_value              TEXT,
    new_value              TEXT,
    message                TEXT         NOT NULL,
    impact                 TEXT         NOT NULL,
    remediation            TEXT         NOT NULL,
    fingerprint            VARCHAR(16)  NOT NULL
);
CREATE INDEX ix_findings_scan_position ON findings (scan_id, position);
CREATE INDEX ix_findings_scan_severity ON findings (scan_id, severity);
