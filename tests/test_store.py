"""
Tests for the ReportStore persistence layer.
Redis and PostgreSQL clients are mocked — tests run without any running services.
"""

import json
import uuid
import pytest
from unittest.mock import patch, MagicMock, PropertyMock


def _make_report(name="Store Test User"):
    return {
        "report_id":    str(uuid.uuid4()),
        "name":         name,
        "generated_at": "June 22, 2026",
        "summary": {
            "format": "23andme", "mode": "fast",
            "total_variants": 5, "annotated_variants": 5, "pathogenic_count": 1,
        },
        "ancestry":         {"top_population": "European", "composition": []},
        "risk_scores":      [],
        "pharmacogenomics": [],
        "traits":           [],
        "categories":       {},
    }


# ─────────────────────────────────────────────────────────────────────────────
# In-memory fallback (no Redis, no Postgres)
# ─────────────────────────────────────────────────────────────────────────────
class TestInMemoryFallback:
    """When REDIS_URL and DATABASE_URL are not set, store uses the in-memory dict."""

    def _get_store(self):
        # Ensure env vars are absent and reset the singleton
        import store as store_mod
        store_mod._store_instance = None
        with patch.dict("os.environ", {}, clear=False):
            # Remove connection env vars
            import os
            os.environ.pop("REDIS_URL", None)
            os.environ.pop("DATABASE_URL", None)
            s = store_mod.ReportStore()
        return s

    def test_save_and_get_roundtrip(self):
        s = self._get_store()
        report = _make_report()
        rid = s.save(report)
        retrieved = s.get(rid)
        assert retrieved is not None
        assert retrieved["report_id"] == rid
        assert retrieved["name"] == "Store Test User"

    def test_get_unknown_id_returns_none(self):
        s = self._get_store()
        assert s.get("nonexistent-id-xyz") is None

    def test_delete_removes_report(self):
        s = self._get_store()
        report = _make_report()
        rid = s.save(report)
        s.delete(rid)
        assert s.get(rid) is None

    def test_count_increments(self):
        import store as store_mod
        store_mod._MEMORY_STORE.clear()
        s = self._get_store()
        before = s.count()
        s.save(_make_report())
        assert s.count() == before + 1

    def test_save_returns_report_id_string(self):
        s = self._get_store()
        report = _make_report()
        rid = s.save(report)
        assert isinstance(rid, str)
        assert len(rid) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Redis integration
# ─────────────────────────────────────────────────────────────────────────────
class TestRedisIntegration:
    def _get_store_with_mock_redis(self):
        import store as store_mod
        store_mod._store_instance = None

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("store._get_redis", return_value=mock_redis), \
             patch("store._get_pg_conn", return_value=None):
            s = store_mod.ReportStore()
            s._redis = mock_redis
            s._pg    = None
        return s, mock_redis

    def test_save_calls_redis_setex(self):
        s, mock_redis = self._get_store_with_mock_redis()
        report = _make_report()
        s.save(report)
        mock_redis.setex.assert_called_once()
        key = mock_redis.setex.call_args[0][0]
        assert key.startswith("report:")

    def test_redis_ttl_is_applied(self):
        from store import REDIS_TTL_SECONDS
        s, mock_redis = self._get_store_with_mock_redis()
        s.save(_make_report())
        _, ttl, _ = mock_redis.setex.call_args[0]
        assert ttl == REDIS_TTL_SECONDS

    def test_get_hits_redis_first(self):
        s, mock_redis = self._get_store_with_mock_redis()
        report = _make_report()
        rid = report["report_id"]

        mock_redis.get.return_value = json.dumps(report)
        result = s.get(rid)
        mock_redis.get.assert_called_once_with(f"report:{rid}")
        assert result["report_id"] == rid

    def test_get_returns_none_on_cache_miss(self):
        s, mock_redis = self._get_store_with_mock_redis()
        mock_redis.get.return_value = None
        # Also clear memory store for this ID
        import store as store_mod
        store_mod._MEMORY_STORE.pop("nonexistent", None)
        result = s.get("nonexistent")
        assert result is None

    def test_delete_calls_redis_delete(self):
        s, mock_redis = self._get_store_with_mock_redis()
        s.delete("some-id")
        mock_redis.delete.assert_called_once_with("report:some-id")

    def test_redis_error_falls_back_to_memory(self):
        s, mock_redis = self._get_store_with_mock_redis()
        mock_redis.get.side_effect = Exception("Redis connection lost")

        report = _make_report()
        rid = s.save(report)   # saved to memory fallback
        result = s.get(rid)    # Redis fails → memory
        assert result is not None
        assert result["report_id"] == rid


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL integration
# ─────────────────────────────────────────────────────────────────────────────
class TestPostgresIntegration:
    def _get_store_with_mock_pg(self):
        import store as store_mod
        store_mod._store_instance = None

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("store._get_redis", return_value=None), \
             patch("store._get_pg_conn", return_value=mock_conn):
            s = store_mod.ReportStore()
            s._redis = None
            s._pg    = mock_conn
        return s, mock_conn, mock_cursor

    def test_save_calls_pg_insert(self):
        s, mock_conn, mock_cursor = self._get_store_with_mock_pg()
        report = _make_report()
        s.save(report)
        assert mock_conn.cursor.called

    def test_pg_error_does_not_crash_save(self):
        s, mock_conn, mock_cursor = self._get_store_with_mock_pg()
        mock_conn.cursor.side_effect = Exception("PG connection lost")
        # Should not raise — degrades gracefully
        report = _make_report()
        rid = s.save(report)
        assert isinstance(rid, str)


# ─────────────────────────────────────────────────────────────────────────────
# get_store singleton
# ─────────────────────────────────────────────────────────────────────────────
class TestGetStoreSingleton:
    def test_returns_same_instance(self):
        import store as store_mod
        store_mod._store_instance = None
        s1 = store_mod.get_store()
        s2 = store_mod.get_store()
        assert s1 is s2

    def test_returns_report_store_instance(self):
        from store import get_store, ReportStore
        import store as store_mod
        store_mod._store_instance = None
        assert isinstance(get_store(), ReportStore)
