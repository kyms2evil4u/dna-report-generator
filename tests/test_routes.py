"""
Integration tests for Flask routes.
Pipeline calls are mocked so no real parsing/API work happens.
"""

import io
import json
import uuid
import pytest
from unittest.mock import patch, MagicMock


# ── Shared mock pipeline return ───────────────────────────────────────────────
def _mock_report(name="Test User"):
    rid = str(uuid.uuid4())
    return {
        "report_id":    rid,
        "name":         name,
        "generated_at": "June 22, 2026 at 10:00",
        "summary": {
            "format": "23andme", "mode": "fast",
            "total_variants": 10, "annotated_variants": 8, "pathogenic_count": 1,
        },
        "ancestry": {
            "top_population": "European",
            "composition": [{"population": "European", "percentage": 100.0}],
        },
        "risk_scores":      [],
        "pharmacogenomics": [],
        "traits":           [],
        "categories":       {"pathogenic": [], "disease_risk": [], "traits": [],
                             "pharmacogenomics": [], "ancestry": []},
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /
# ─────────────────────────────────────────────────────────────────────────────
class TestIndexRoute:
    def test_returns_200(self, client):
        res = client.get("/")
        assert res.status_code == 200

    def test_contains_html(self, client):
        res = client.get("/")
        assert b"<html" in res.data.lower() or b"<!doctype" in res.data.lower()

    def test_contains_upload_form(self, client):
        res = client.get("/")
        assert b"fileInput" in res.data or b"dropzone" in res.data


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/analyze
# ─────────────────────────────────────────────────────────────────────────────
VALID_23ANDME = (
    b"# rsid\tchromosome\tposition\tgenotype\n"
    b"rs4244285\t10\t96541616\tAG\n"
    b"rs7903146\t10\t114758349\tCT\n"
)


class TestAnalyzeRoute:
    def test_no_file_returns_400(self, client):
        res = client.post("/api/analyze")
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_wrong_extension_returns_400(self, client):
        res = client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(b"data"), "dna.exe")},
            content_type="multipart/form-data",
        )
        assert res.status_code == 400

    @patch("app.run_full_pipeline")
    def test_valid_upload_returns_report_id(self, mock_pipeline, client):
        report = _mock_report()
        mock_pipeline.return_value = report

        res = client.post(
            "/api/analyze",
            data={
                "file": (io.BytesIO(VALID_23ANDME), "dna.txt"),
                "name": "Test User",
                "mode": "fast",
                "max_variants": "100",
            },
            content_type="multipart/form-data",
        )
        assert res.status_code == 200
        body = json.loads(res.data)
        assert "report_id" in body
        assert body["status"] == "success"

    @patch("app.run_full_pipeline")
    def test_pipeline_error_returns_500(self, mock_pipeline, client):
        mock_pipeline.side_effect = Exception("Something went wrong")

        res = client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(VALID_23ANDME), "dna.txt")},
            content_type="multipart/form-data",
        )
        assert res.status_code == 500
        body = json.loads(res.data)
        assert "error" in body

    @patch("app.run_full_pipeline")
    def test_value_error_returns_400(self, mock_pipeline, client):
        mock_pipeline.side_effect = ValueError("Unsupported format")

        res = client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(VALID_23ANDME), "dna.txt")},
            content_type="multipart/form-data",
        )
        assert res.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/sample
# ─────────────────────────────────────────────────────────────────────────────
class TestSampleRoute:
    @patch("app.generate_sample_variants")
    @patch("app.normalize_variants")
    @patch("app.annotate_variants")
    @patch("app.categorize_variants")
    @patch("app.compute_ancestry")
    @patch("app.compute_risk_scores")
    @patch("app.analyze_pharmacogenomics")
    @patch("app.analyze_traits")
    def test_returns_report_id(
        self, mock_traits, mock_pgx, mock_risk, mock_anc,
        mock_cats, mock_ann, mock_norm, mock_gen, client
    ):
        report = _mock_report("Demo User")
        mock_gen.return_value   = []
        mock_norm.return_value  = []
        mock_ann.return_value   = []
        mock_cats.return_value  = report["categories"]
        mock_anc.return_value   = report["ancestry"]
        mock_risk.return_value  = []
        mock_pgx.return_value   = []
        mock_traits.return_value= []

        res = client.get("/api/sample?name=Demo+User&mode=fast")
        assert res.status_code == 200
        body = json.loads(res.data)
        assert "report_id" in body


# ─────────────────────────────────────────────────────────────────────────────
# GET /report/<report_id>
# ─────────────────────────────────────────────────────────────────────────────
class TestReportRoute:
    @patch("app.run_full_pipeline")
    def test_valid_report_id_returns_200(self, mock_pipeline, client):
        report = _mock_report()
        mock_pipeline.return_value = report

        # First create the report via /api/analyze
        client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(VALID_23ANDME), "dna.txt"), "name": "Test"},
            content_type="multipart/form-data",
        )
        rid = report["report_id"]

        res = client.get(f"/report/{rid}")
        assert res.status_code == 200

    def test_unknown_report_id_returns_404(self, client):
        res = client.get("/report/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# GET /report/<id>/json
# ─────────────────────────────────────────────────────────────────────────────
class TestJsonExportRoute:
    @patch("app.run_full_pipeline")
    def test_json_export_valid_report(self, mock_pipeline, client):
        report = _mock_report()
        mock_pipeline.return_value = report

        client.post(
            "/api/analyze",
            data={"file": (io.BytesIO(VALID_23ANDME), "dna.txt"), "name": "Test"},
            content_type="multipart/form-data",
        )
        rid = report["report_id"]

        res = client.get(f"/report/{rid}/json")
        assert res.status_code == 200
        assert res.content_type == "application/json"
        body = json.loads(res.data)
        assert body["report_id"] == rid

    def test_json_export_unknown_id_returns_404(self, client):
        res = client.get("/report/nonexistent-id/json")
        assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/health
# ─────────────────────────────────────────────────────────────────────────────
class TestHealthRoute:
    def test_returns_200(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200

    def test_returns_ok_status(self, client):
        body = json.loads(client.get("/api/health").data)
        assert body["status"] == "ok"
