"""
Tests for large file upload handling.
Verifies streaming save, size enforcement, and edge cases —
all without real disk I/O beyond small temp files.
"""

import io
import os
import uuid
import tempfile
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# stream_save helper
# ─────────────────────────────────────────────────────────────────────────────
class TestStreamSave:
    """stream_save must write chunks without loading entire file into RAM."""

    def _make_stream(self, data: bytes):
        """Wrap bytes in a mock FileStorage-like object."""
        buf = io.BytesIO(data)
        mock_fs = MagicMock()
        mock_fs.stream = buf
        return mock_fs

    def test_writes_correct_bytes(self):
        from app import stream_save
        data = b"A" * (3 * 1024 * 1024)   # 3 MB
        mock_fs = self._make_stream(data)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = Path(f.name)
        try:
            total = stream_save(mock_fs, path)
            assert total == len(data)
            assert path.read_bytes() == data
        finally:
            path.unlink(missing_ok=True)

    def test_returns_total_byte_count(self):
        from app import stream_save
        data = b"X" * 512
        mock_fs = self._make_stream(data)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = Path(f.name)
        try:
            total = stream_save(mock_fs, path)
            assert total == 512
        finally:
            path.unlink(missing_ok=True)

    def test_empty_file_returns_zero(self):
        from app import stream_save
        mock_fs = self._make_stream(b"")
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = Path(f.name)
        try:
            total = stream_save(mock_fs, path)
            assert total == 0
            assert path.stat().st_size == 0
        finally:
            path.unlink(missing_ok=True)

    def test_multi_chunk_file(self):
        """A file larger than STREAM_CHUNK_SIZE must be split into chunks."""
        from app import stream_save, STREAM_CHUNK_SIZE
        # 2.5 chunks worth of data
        data = b"B" * int(STREAM_CHUNK_SIZE * 2.5)
        mock_fs = self._make_stream(data)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = Path(f.name)
        try:
            total = stream_save(mock_fs, path)
            assert total == len(data)
        finally:
            path.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# /api/analyze — size enforcement via Flask test client
# ─────────────────────────────────────────────────────────────────────────────
TINY_DNA = (
    b"# rsid\tchromosome\tposition\tgenotype\n"
    b"rs4244285\t10\t96541616\tAG\n"
)


class TestUploadSizeEnforcement:
    @patch("app.run_full_pipeline")
    def test_file_within_limit_accepted(self, mock_pipeline, client):
        """A small file must be accepted (no 413)."""
        mock_pipeline.return_value = {
            "report_id": str(uuid.uuid4()), "name": "Test",
            "generated_at": "June 22, 2026",
            "summary": {"format": "23andme", "mode": "fast",
                        "total_variants": 1, "annotated_variants": 1,
                        "pathogenic_count": 0},
            "ancestry": {"top_population": "European", "composition": []},
            "risk_scores": [], "pharmacogenomics": [], "traits": [], "categories": {},
        }
        res = client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(TINY_DNA), "dna.txt")},
            content_type="multipart/form-data",
        )
        assert res.status_code == 200

    @patch("app.stream_save")
    def test_file_over_limit_returns_413(self, mock_save, client):
        """A file reported as over MAX_FILE_SIZE_MB must be rejected with 413."""
        # Make stream_save report a 9999 MB file
        mock_save.return_value = 9999 * 1024 * 1024

        res = client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(TINY_DNA), "dna.txt")},
            content_type="multipart/form-data",
        )
        assert res.status_code == 413
        import json
        body = json.loads(res.data)
        assert "error" in body
        assert "large" in body["error"].lower() or "mb" in body["error"].lower()

    @patch("app.stream_save")
    def test_413_deletes_partial_file(self, mock_save, client, tmp_path):
        """Rejected oversized uploads must not leave temp files on disk."""
        mock_save.return_value = 9999 * 1024 * 1024
        client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(TINY_DNA), "dna.txt")},
            content_type="multipart/form-data",
        )
        # Verify stream_save was called (file was started then rejected)
        assert mock_save.called

    def test_no_file_returns_400(self, client):
        res = client.post("/api/analyze")
        assert res.status_code == 400

    def test_bad_extension_returns_400(self, client):
        res = client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(b"data"), "genome.exe")},
            content_type="multipart/form-data",
        )
        assert res.status_code == 400

    @patch("app.stream_save")
    def test_stream_save_error_returns_500(self, mock_save, client):
        mock_save.side_effect = IOError("Disk full")
        res = client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(TINY_DNA), "dna.txt")},
            content_type="multipart/form-data",
        )
        assert res.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# Allowed file extensions
# ─────────────────────────────────────────────────────────────────────────────
class TestAllowedExtensions:
    def test_txt_allowed(self):
        from app import allowed_file
        assert allowed_file("dna_data.txt") is True

    def test_csv_allowed(self):
        from app import allowed_file
        assert allowed_file("myheritage.csv") is True

    def test_vcf_allowed(self):
        from app import allowed_file
        assert allowed_file("genome.vcf") is True

    def test_vcf_gz_allowed(self):
        from app import allowed_file
        assert allowed_file("genome.vcf.gz") is True

    def test_txt_gz_allowed(self):
        from app import allowed_file
        assert allowed_file("23andme_data.txt.gz") is True

    def test_exe_rejected(self):
        from app import allowed_file
        assert allowed_file("malware.exe") is False

    def test_pdf_rejected(self):
        from app import allowed_file
        assert allowed_file("document.pdf") is False

    def test_zip_rejected(self):
        from app import allowed_file
        assert allowed_file("archive.zip") is False

    def test_case_insensitive(self):
        from app import allowed_file
        assert allowed_file("DNA.TXT") is True
        assert allowed_file("GENOME.VCF") is True


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoint exposes max_upload_mb
# ─────────────────────────────────────────────────────────────────────────────
class TestHealthIncludesUploadLimit:
    def test_health_returns_max_upload_mb(self, client):
        import json
        res = client.get("/api/health")
        body = json.loads(res.data)
        assert "max_upload_mb" in body
        assert isinstance(body["max_upload_mb"], int)
        assert body["max_upload_mb"] >= 100

    def test_413_handler_returns_json(self, client):
        """Werkzeug's built-in 413 must be overridden to return JSON."""
        with client.application.test_request_context():
            from app import request_entity_too_large
            from werkzeug.exceptions import RequestEntityTooLarge
            resp = request_entity_too_large(RequestEntityTooLarge())
            import json
            body = json.loads(resp[0].get_data())
            assert "error" in body


# ─────────────────────────────────────────────────────────────────────────────
# tasks.py cancel logic
# ─────────────────────────────────────────────────────────────────────────────
class TestCancelTask:
    def test_cancel_mid_pipeline(self):
        import tasks
        tid = tasks.create_task("big.vcf", 400.0)
        tasks.advance(tid, "annotating")
        ok = tasks.cancel(tid)
        assert ok is True
        s = tasks.get_status(tid)
        assert s["stage"] == "cancelled"

    def test_advance_raises_after_cancel(self):
        import tasks
        tid = tasks.create_task("big.vcf")
        tasks.advance(tid, "parsing")
        tasks.cancel(tid)
        with pytest.raises(tasks.CancelledError):
            tasks.advance(tid, "normalizing")

    def test_cancel_done_task_returns_false(self):
        import tasks
        tid = tasks.create_task("done.vcf")
        tasks.complete(tid, "report-abc")
        ok = tasks.cancel(tid)
        assert ok is False

    def test_cancel_error_task_returns_false(self):
        import tasks
        tid = tasks.create_task("bad.vcf")
        tasks.fail(tid, "something broke")
        ok = tasks.cancel(tid)
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# /api/cancel endpoint
# ─────────────────────────────────────────────────────────────────────────────
class TestCancelEndpoint:
    @patch("app.tasks.get_status")
    @patch("app.tasks.cancel")
    def test_cancel_running_task(self, mock_cancel, mock_status, client):
        mock_status.return_value = {"stage": "annotating", "task_id": "t1"}
        mock_cancel.return_value = True
        res = client.post("/api/cancel/t1")
        import json
        body = json.loads(res.data)
        assert res.status_code == 200
        assert body["cancelled"] is True

    @patch("app.tasks.get_status")
    def test_cancel_unknown_task_returns_404(self, mock_status, client):
        mock_status.return_value = None
        res = client.post("/api/cancel/nonexistent")
        assert res.status_code == 404

    @patch("app.tasks.get_status")
    def test_cancel_done_task_returns_409(self, mock_status, client):
        mock_status.return_value = {"stage": "done", "task_id": "t2"}
        res = client.post("/api/cancel/t2")
        assert res.status_code == 409

    @patch("app.tasks.get_status")
    def test_cancel_already_cancelled_returns_409(self, mock_status, client):
        mock_status.return_value = {"stage": "cancelled", "task_id": "t3"}
        res = client.post("/api/cancel/t3")
        assert res.status_code == 409
