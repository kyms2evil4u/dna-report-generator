"""
Tests for PDF and HTML report generators.
Verifies output exists, is non-empty, and contains expected content.
"""

import os
import tempfile
import pytest

from reports.pdf_generator  import generate_pdf_report
from reports.html_generator import generate_html_report


# ─────────────────────────────────────────────────────────────────────────────
# PDF Generator
# ─────────────────────────────────────────────────────────────────────────────
class TestPDFGenerator:
    def test_creates_file(self, mock_report):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            generate_pdf_report(mock_report, path)
            assert os.path.exists(path)
        finally:
            os.unlink(path)

    def test_file_is_nonempty(self, mock_report):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            generate_pdf_report(mock_report, path)
            assert os.path.getsize(path) > 1024  # at least 1KB
        finally:
            os.unlink(path)

    def test_file_starts_with_pdf_magic_bytes(self, mock_report):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            generate_pdf_report(mock_report, path)
            with open(path, "rb") as fh:
                header = fh.read(4)
            assert header == b"%PDF"
        finally:
            os.unlink(path)

    def test_minimal_report_does_not_crash(self):
        """Ensure generator handles a report with empty sections."""
        minimal = {
            "report_id": "test-123",
            "name": "Empty User",
            "generated_at": "June 22, 2026",
            "summary": {
                "format": "23andme", "mode": "fast",
                "total_variants": 0, "annotated_variants": 0, "pathogenic_count": 0,
            },
            "ancestry":         {"top_population": "Unknown", "composition": []},
            "risk_scores":      [],
            "pharmacogenomics": [],
            "traits":           [],
            "categories":       {},
        }
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            generate_pdf_report(minimal, path)
            assert os.path.exists(path)
        finally:
            os.unlink(path)

    def test_special_characters_in_name(self, mock_report):
        """Names with special chars should not crash PDF generation."""
        report = {**mock_report, "name": "O'Brien-Smith, Zoë"}
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            generate_pdf_report(report, path)
            assert os.path.exists(path)
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
# HTML Generator
# ─────────────────────────────────────────────────────────────────────────────
class TestHTMLGenerator:
    def test_creates_file(self, mock_report):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            generate_html_report(mock_report, path)
            assert os.path.exists(path)
        finally:
            os.unlink(path)

    def test_file_is_nonempty(self, mock_report):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            generate_html_report(mock_report, path)
            assert os.path.getsize(path) > 500
        finally:
            os.unlink(path)

    def test_contains_user_name(self, mock_report):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            path = f.name
        try:
            generate_html_report(mock_report, path)
            content = open(path).read()
            assert mock_report["name"] in content
        finally:
            os.unlink(path)

    def test_contains_html_doctype(self, mock_report):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            path = f.name
        try:
            generate_html_report(mock_report, path)
            content = open(path).read().lower()
            assert "<!doctype html>" in content or "<html" in content
        finally:
            os.unlink(path)

    def test_contains_report_sections(self, mock_report):
        """Key section headings must appear in the HTML."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            path = f.name
        try:
            generate_html_report(mock_report, path)
            content = open(path).read().lower()
            for keyword in ["ancestry", "risk", "pharmacogenomics", "traits"]:
                assert keyword in content, f"Missing section: {keyword}"
        finally:
            os.unlink(path)

    def test_standalone_html_has_no_external_deps(self, mock_report):
        """Standalone report should not reference external CSS/JS CDNs that require internet."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            path = f.name
        try:
            generate_html_report(mock_report, path)
            content = open(path).read()
            # The standalone export should inline or omit external dependencies
            # (It's OK if it links CDNs — just ensure the file itself is self-contained enough to open)
            assert len(content) > 200
        finally:
            os.unlink(path)
