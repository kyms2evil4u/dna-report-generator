"""
Report Store — persistent backend replacing the in-memory dict.

Strategy:
  - Primary cache:  Redis (fast reads, TTL-based expiry)
  - Durable store:  PostgreSQL (metadata + variants for querying/audit)
  - Fallback:       In-memory dict (development / no-DB mode)

Usage:
    from store import ReportStore
    store = ReportStore()          # auto-detects env vars
    store.save(report_data)
    data = store.get(report_id)
    store.delete(report_id)
"""

import os
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# TTL for Redis cache: 24 hours
REDIS_TTL_SECONDS = 86400

# Report expiry in Postgres: 7 days (None = keep forever)
PG_REPORT_TTL_DAYS: Optional[int] = int(os.environ.get("REPORT_TTL_DAYS", 7))


# ── Redis client ──────────────────────────────────────────────────────────────
def _get_redis():
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    try:
        import redis
        client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=3)
        client.ping()
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable: {e} — falling back to in-memory store")
        return None


# ── Postgres client ───────────────────────────────────────────────────────────
def _get_pg_conn():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.warning(f"PostgreSQL unavailable: {e} — report metadata will not be persisted")
        return None


# ── In-memory fallback ────────────────────────────────────────────────────────
_MEMORY_STORE: Dict[str, dict] = {}


class ReportStore:
    """
    Unified report store with Redis cache + PostgreSQL persistence.
    Degrades gracefully if either backend is unavailable.
    """

    def __init__(self):
        self._redis = _get_redis()
        self._pg    = _get_pg_conn()
        mode = []
        if self._redis:
            mode.append("Redis")
        if self._pg:
            mode.append("PostgreSQL")
        if not mode:
            mode.append("in-memory")
        logger.info(f"ReportStore initialized: {' + '.join(mode)}")

    # ── Public API ──────────────────────────────────────────────────────────

    # ── Dict-like interface (used by app.py as REPORT_STORE[id] = data) ────
    def __setitem__(self, report_id: str, report_data: dict) -> None:
        self.save(report_data)

    def __getitem__(self, report_id: str):
        result = self.get(report_id)
        if result is None:
            raise KeyError(report_id)
        return result

    def __contains__(self, report_id: str) -> bool:
        return self.get(report_id) is not None

    def save(self, report_data: dict) -> str:
        """
        Persist a report. Returns the report_id.
        Writes to Redis (cache) and PostgreSQL (durable) in parallel.
        """
        report_id = report_data.get("report_id") or str(uuid.uuid4())
        report_data["report_id"] = report_id

        # 1. Redis cache
        self._redis_set(report_id, report_data)

        # 2. PostgreSQL durable store
        self._pg_insert(report_data)

        # 3. In-memory fallback
        _MEMORY_STORE[report_id] = report_data

        return report_id

    def get(self, report_id: str) -> Optional[dict]:
        """
        Retrieve a report by ID.
        Checks Redis first, then PostgreSQL, then memory.
        """
        # 1. Redis
        data = self._redis_get(report_id)
        if data:
            return data

        # 2. PostgreSQL
        data = self._pg_get(report_id)
        if data:
            # Re-warm Redis cache
            self._redis_set(report_id, data)
            return data

        # 3. Memory fallback
        return _MEMORY_STORE.get(report_id)

    def delete(self, report_id: str):
        """Delete a report from all backends."""
        self._redis_delete(report_id)
        self._pg_delete(report_id)
        _MEMORY_STORE.pop(report_id, None)

    def list_recent(self, limit: int = 20) -> list:
        """Return the most recent report metadata records from PostgreSQL."""
        if not self._pg:
            return list(_MEMORY_STORE.values())[-limit:]
        try:
            import psycopg2.extras
            with self._pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name, generated_at, file_format, analysis_mode,
                           total_variants, pathogenic_count, top_ancestry
                    FROM reports
                    ORDER BY generated_at DESC
                    LIMIT %s
                """, (limit,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"PG list_recent error: {e}")
            return []

    def count(self) -> int:
        if self._pg:
            try:
                with self._pg.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM reports")
                    return cur.fetchone()[0]
            except Exception:
                pass
        return len(_MEMORY_STORE)

    # ── Redis helpers ───────────────────────────────────────────────────────

    def _redis_set(self, report_id: str, data: dict):
        if not self._redis:
            return
        try:
            self._redis.setex(
                f"report:{report_id}",
                REDIS_TTL_SECONDS,
                json.dumps(data, default=str),
            )
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")

    def _redis_get(self, report_id: str) -> Optional[dict]:
        if not self._redis:
            return None
        try:
            raw = self._redis.get(f"report:{report_id}")
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    def _redis_delete(self, report_id: str):
        if not self._redis:
            return
        try:
            self._redis.delete(f"report:{report_id}")
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")

    # ── PostgreSQL helpers ──────────────────────────────────────────────────

    def _pg_insert(self, report_data: dict):
        if not self._pg:
            return
        try:
            import psycopg2.extras
            report_id  = report_data["report_id"]
            summary    = report_data.get("summary", {})
            ancestry   = report_data.get("ancestry", {})
            expires_at = (
                datetime.utcnow() + timedelta(days=PG_REPORT_TTL_DAYS)
                if PG_REPORT_TTL_DAYS else None
            )

            with self._pg.cursor() as cur:
                # Upsert report metadata
                cur.execute("""
                    INSERT INTO reports
                        (id, name, generated_at, file_format, analysis_mode,
                         total_variants, pathogenic_count, top_ancestry,
                         summary_json, expires_at)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name             = EXCLUDED.name,
                        file_format      = EXCLUDED.file_format,
                        analysis_mode    = EXCLUDED.analysis_mode,
                        total_variants   = EXCLUDED.total_variants,
                        pathogenic_count = EXCLUDED.pathogenic_count,
                        top_ancestry     = EXCLUDED.top_ancestry,
                        summary_json     = EXCLUDED.summary_json
                """, (
                    report_id,
                    report_data.get("name", "User"),
                    summary.get("format"),
                    summary.get("mode", "fast"),
                    summary.get("total_variants", 0),
                    summary.get("pathogenic_count", 0),
                    ancestry.get("top_population"),
                    json.dumps(summary, default=str),
                    expires_at,
                ))

                # Insert variants (all categories flattened)
                categories = report_data.get("categories", {})
                all_variants = [
                    v for cat_variants in categories.values()
                    for v in cat_variants
                ]
                if all_variants:
                    psycopg2.extras.execute_batch(cur, """
                        INSERT INTO variants
                            (report_id, rsid, chromosome, position, genotype,
                             allele1, allele2, gene, consequence, clinical_significance,
                             cadd_score, revel_score, gnomad_af, gnomad_af_popmax,
                             category, source_format, annotation_json)
                        VALUES (%(report_id)s, %(rsid)s, %(chromosome)s, %(position)s,
                                %(genotype)s, %(allele1)s, %(allele2)s, %(gene)s,
                                %(consequence)s, %(clinical_significance)s,
                                %(cadd_score)s, %(revel_score)s, %(gnomad_af)s,
                                %(gnomad_af_popmax)s, %(category)s, %(source_format)s,
                                %(annotation_json)s)
                        ON CONFLICT DO NOTHING
                    """, [
                        {
                            "report_id":             report_id,
                            "rsid":                  v.get("rsid"),
                            "chromosome":            v.get("chromosome"),
                            "position":              v.get("position"),
                            "genotype":              v.get("genotype"),
                            "allele1":               v.get("allele1"),
                            "allele2":               v.get("allele2"),
                            "gene":                  v.get("gene"),
                            "consequence":           v.get("consequence"),
                            "clinical_significance": v.get("clinical_significance"),
                            "cadd_score":            v.get("cadd_score"),
                            "revel_score":           v.get("revel_score"),
                            "gnomad_af":             v.get("gnomad_af"),
                            "gnomad_af_popmax":      v.get("gnomad_af_popmax"),
                            "category":              v.get("category"),
                            "source_format":         v.get("source_format"),
                            "annotation_json":       json.dumps(v, default=str),
                        }
                        for v in all_variants
                    ], page_size=500)

                # Insert risk scores
                risk_scores = report_data.get("risk_scores", [])
                if risk_scores:
                    psycopg2.extras.execute_batch(cur, """
                        INSERT INTO risk_scores
                            (report_id, condition, risk_tier, risk_label,
                             relative_risk, adjusted_risk_pct, baseline_risk_pct,
                             prs, snps_analyzed, snps_total)
                        VALUES (%(report_id)s, %(condition)s, %(risk_tier)s,
                                %(risk_label)s, %(relative_risk)s, %(adjusted_risk_pct)s,
                                %(baseline_risk_pct)s, %(prs)s,
                                %(snps_analyzed)s, %(snps_total)s)
                    """, [{"report_id": report_id, **rs} for rs in risk_scores])

                # Insert PGx
                pgx = report_data.get("pharmacogenomics", [])
                if pgx:
                    psycopg2.extras.execute_batch(cur, """
                        INSERT INTO pharmacogenomics
                            (report_id, rsid, gene, star_allele, your_genotype,
                             drugs_affected, effect, severity)
                        VALUES (%(report_id)s, %(rsid)s, %(gene)s, %(star_allele)s,
                                %(your_genotype)s, %(drugs_affected)s,
                                %(effect)s, %(severity)s)
                    """, [{"report_id": report_id, **p} for p in pgx])

                # Audit log
                cur.execute("""
                    INSERT INTO audit_log (event, report_id)
                    VALUES ('report_created', %s)
                """, (report_id,))

        except Exception as e:
            logger.error(f"PostgreSQL insert error: {e}")

    def _pg_get(self, report_id: str) -> Optional[dict]:
        """
        Reconstruct a report dict from PostgreSQL.
        Note: returns the summary_json blob, not full variant detail —
        for the full report use Redis or the in-memory fallback.
        """
        if not self._pg:
            return None
        try:
            import psycopg2.extras
            with self._pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
                row = cur.fetchone()
                if not row:
                    return None
                # Return a lightweight stub — caller will re-render if needed
                return {
                    "report_id":    str(row["id"]),
                    "name":         row["name"],
                    "generated_at": str(row["generated_at"]),
                    "summary":      row.get("summary_json") or {},
                    "ancestry":     {"top_population": row.get("top_ancestry")},
                    "risk_scores":  [],
                    "pharmacogenomics": [],
                    "traits":       [],
                    "categories":   {},
                    "_partial":     True,   # flag: full data not available
                }
        except Exception as e:
            logger.error(f"PostgreSQL get error: {e}")
            return None

    def _pg_delete(self, report_id: str):
        if not self._pg:
            return
        try:
            with self._pg.cursor() as cur:
                cur.execute("DELETE FROM reports WHERE id = %s", (report_id,))
        except Exception as e:
            logger.error(f"PostgreSQL delete error: {e}")


# ── Module-level singleton ─────────────────────────────────────────────────────
_store_instance: Optional[ReportStore] = None


def get_store() -> ReportStore:
    """Return the module-level singleton ReportStore."""
    global _store_instance
    if _store_instance is None:
        _store_instance = ReportStore()
    return _store_instance
