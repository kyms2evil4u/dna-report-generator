-- ─────────────────────────────────────────────────────────────────
-- DNA Report Generator — PostgreSQL Schema
-- Auto-run by Postgres on first container start
-- ─────────────────────────────────────────────────────────────────

-- Enable useful extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- fast text search on rsids/genes

-- ── reports ───────────────────────────────────────────────────────
-- Stores metadata for every generated report.
-- The full JSON payload lives in Redis; this table is the durable record.
CREATE TABLE IF NOT EXISTS reports (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT        NOT NULL DEFAULT 'User',
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    file_format     TEXT,
    analysis_mode   TEXT        DEFAULT 'fast',
    total_variants  INTEGER     DEFAULT 0,
    pathogenic_count INTEGER    DEFAULT 0,
    top_ancestry    TEXT,
    summary_json    JSONB,          -- lightweight summary only
    expires_at      TIMESTAMPTZ     -- NULL = keep forever
);

CREATE INDEX IF NOT EXISTS idx_reports_generated_at ON reports (generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_expires_at   ON reports (expires_at)
    WHERE expires_at IS NOT NULL;

-- ── variants ──────────────────────────────────────────────────────
-- Normalized, annotated variants for each report.
-- Partitioned by report_id for efficient per-report queries.
CREATE TABLE IF NOT EXISTS variants (
    id                    BIGSERIAL   PRIMARY KEY,
    report_id             UUID        NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    rsid                  TEXT        NOT NULL,
    chromosome            TEXT,
    position              INTEGER,
    genotype              TEXT,
    allele1               TEXT,
    allele2               TEXT,
    gene                  TEXT,
    consequence           TEXT,
    clinical_significance TEXT,
    cadd_score            NUMERIC(6,2),
    revel_score           NUMERIC(6,4),
    gnomad_af             NUMERIC(10,8),
    gnomad_af_popmax      NUMERIC(10,8),
    category              TEXT,
    source_format         TEXT,
    annotation_json       JSONB       -- full annotation blob
);

CREATE INDEX IF NOT EXISTS idx_variants_report_id  ON variants (report_id);
CREATE INDEX IF NOT EXISTS idx_variants_rsid        ON variants (rsid);
CREATE INDEX IF NOT EXISTS idx_variants_category    ON variants (category);
CREATE INDEX IF NOT EXISTS idx_variants_gene        ON variants USING GIN (gene gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_variants_cadd        ON variants (cadd_score DESC NULLS LAST);

-- ── risk_scores ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_scores (
    id              BIGSERIAL   PRIMARY KEY,
    report_id       UUID        NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    condition       TEXT        NOT NULL,
    risk_tier       TEXT,
    risk_label      TEXT,
    relative_risk   NUMERIC(6,3),
    adjusted_risk_pct NUMERIC(5,1),
    baseline_risk_pct NUMERIC(5,1),
    prs             NUMERIC(8,4),
    snps_analyzed   INTEGER,
    snps_total      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_risk_report_id ON risk_scores (report_id);

-- ── pharmacogenomics ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pharmacogenomics (
    id              BIGSERIAL   PRIMARY KEY,
    report_id       UUID        NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    rsid            TEXT,
    gene            TEXT,
    star_allele     TEXT,
    your_genotype   TEXT,
    drugs_affected  TEXT[],
    effect          TEXT,
    severity        TEXT
);

CREATE INDEX IF NOT EXISTS idx_pgx_report_id ON pharmacogenomics (report_id);

-- ── audit_log ─────────────────────────────────────────────────────
-- Lightweight audit trail: who generated what, when
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL   PRIMARY KEY,
    event       TEXT        NOT NULL,
    report_id   UUID,
    ip_address  TEXT,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_report_id  ON audit_log (report_id);

-- ── Cleanup function ──────────────────────────────────────────────
-- Call via cron or pg_cron to auto-expire old reports
CREATE OR REPLACE FUNCTION cleanup_expired_reports()
RETURNS INTEGER AS $$
DECLARE
    deleted INTEGER;
BEGIN
    DELETE FROM reports WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RETURN deleted;
END;
$$ LANGUAGE plpgsql;
