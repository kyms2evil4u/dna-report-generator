"""
Flask Web Application — DNA Report Generator
Routes: landing page, file upload/analysis, report viewer, exports
"""

import os
import uuid
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, request, jsonify, render_template,
    send_file, abort, session,
)
from flask_cors import CORS
from werkzeug.utils import secure_filename

from parsers import detect_format, parse_23andme, parse_ancestry, parse_myheritage, parse_vcf, normalize_variants
from api import annotate_variants
from analysis import categorize_variants, compute_ancestry, compute_risk_scores, analyze_pharmacogenomics, analyze_traits
from reports import generate_pdf_report, generate_html_report
from data.sample_generator import generate_sample_variants

# ── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32))
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".txt", ".csv", ".vcf"}
MAX_FILE_SIZE_MB   = 100
UPLOAD_FOLDER      = Path(tempfile.gettempdir()) / "dna_uploads"
REPORTS_FOLDER     = Path(tempfile.gettempdir()) / "dna_reports"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)

# In-memory report store (keyed by report_id)
# In production, swap for Redis or a database
REPORT_STORE: dict = {}


# ── Helpers ──────────────────────────────────────────────────────────────────
def allowed_file(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def parse_file(filepath: str, fmt: str) -> list:
    parsers = {
        "23andme":   parse_23andme,
        "ancestry":  parse_ancestry,
        "myheritage":parse_myheritage,
        "vcf":       parse_vcf,
    }
    parser = parsers.get(fmt)
    if not parser:
        raise ValueError(f"Unsupported format: {fmt}")
    return parser(filepath)


def run_full_pipeline(
    filepath: str,
    name: str = "User",
    mode: str = "fast",
    max_variants: int = 500,
) -> dict:
    """
    Full analysis pipeline:
    parse → normalize → annotate → categorize → score → report data
    """
    # 1. Detect format
    fmt = detect_format(filepath)
    logger.info(f"Detected format: {fmt}")
    if fmt == "unknown":
        raise ValueError("Could not detect file format. Please ensure the file is a valid 23andMe, AncestryDNA, MyHeritage, or VCF export.")

    # 2. Parse
    raw_variants = parse_file(filepath, fmt)
    logger.info(f"Parsed {len(raw_variants)} raw variants")

    # 3. Normalize
    variants = normalize_variants(raw_variants)
    logger.info(f"Normalized to {len(variants)} clean variants")

    if len(variants) == 0:
        raise ValueError("No valid variants found after normalization. Check the file format.")

    # 4. Annotate via APIs
    annotated = annotate_variants(variants, mode=mode, max_variants=max_variants)

    # 5. Categorize
    categories = categorize_variants(annotated)

    # 6. Ancestry
    ancestry = compute_ancestry(annotated)

    # 7. Risk scores
    risk_scores = compute_risk_scores(annotated)

    # 8. PGx
    pgx = analyze_pharmacogenomics(annotated)

    # 9. Traits
    traits = analyze_traits(annotated)

    # 10. Assemble report data
    pathogenic_count = len(categories.get("pathogenic", []))

    report_data = {
        "report_id": str(uuid.uuid4()),
        "name": name,
        "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
        "summary": {
            "format": fmt,
            "mode": mode,
            "total_variants": len(variants),
            "annotated_variants": len(annotated),
            "pathogenic_count": pathogenic_count,
        },
        "ancestry": ancestry,
        "risk_scores": risk_scores,
        "pharmacogenomics": pgx,
        "traits": traits,
        "categories": categories,
    }

    return report_data


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Accepts a multipart file upload, runs the full pipeline,
    stores the report, returns {report_id}.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not allowed_file(f.filename):
        return jsonify({"error": "File type not supported. Use .txt, .csv, or .vcf"}), 400

    # Size check
    f.seek(0, 2)
    size_mb = f.tell() / (1024 * 1024)
    f.seek(0)
    if size_mb > MAX_FILE_SIZE_MB:
        return jsonify({"error": f"File too large ({size_mb:.1f} MB). Max is {MAX_FILE_SIZE_MB} MB."}), 413

    name         = request.form.get("name", "User").strip() or "User"
    mode         = request.form.get("mode", "fast")
    max_variants = int(request.form.get("max_variants", 500))

    # Save upload to temp file
    filename = secure_filename(f.filename)
    filepath = UPLOAD_FOLDER / f"{uuid.uuid4()}_{filename}"
    f.save(str(filepath))

    try:
        report_data = run_full_pipeline(
            str(filepath),
            name=name,
            mode=mode,
            max_variants=max_variants,
        )
        report_id = report_data["report_id"]
        REPORT_STORE[report_id] = report_data
        logger.info(f"Report {report_id} generated for '{name}'")
        return jsonify({"report_id": report_id, "status": "success"})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Pipeline error")
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500
    finally:
        try:
            filepath.unlink()
        except Exception:
            pass


@app.route("/api/sample")
def sample():
    """
    Generates a report from built-in sample data (no file upload needed).
    """
    name = request.args.get("name", "Demo User")
    mode = request.args.get("mode", "fast")

    try:
        sample_variants = generate_sample_variants()
        variants        = normalize_variants(sample_variants)
        annotated       = annotate_variants(variants, mode=mode, max_variants=100)
        categories      = categorize_variants(annotated)
        ancestry        = compute_ancestry(annotated)
        risk_scores     = compute_risk_scores(annotated)
        pgx             = analyze_pharmacogenomics(annotated)
        traits          = analyze_traits(annotated)

        report_data = {
            "report_id": str(uuid.uuid4()),
            "name": name,
            "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "summary": {
                "format": "sample",
                "mode": mode,
                "total_variants": len(variants),
                "annotated_variants": len(annotated),
                "pathogenic_count": len(categories.get("pathogenic", [])),
            },
            "ancestry": ancestry,
            "risk_scores": risk_scores,
            "pharmacogenomics": pgx,
            "traits": traits,
            "categories": categories,
        }

        report_id = report_data["report_id"]
        REPORT_STORE[report_id] = report_data
        return jsonify({"report_id": report_id, "status": "success"})

    except Exception as e:
        logger.exception("Sample pipeline error")
        return jsonify({"error": str(e)}), 500


@app.route("/report/<report_id>")
def view_report(report_id: str):
    """Render the interactive HTML dashboard for a report."""
    report_data = REPORT_STORE.get(report_id)
    if not report_data:
        abort(404)
    report_json = json.dumps(report_data, default=str)
    return render_template("report.html", report=report_data, report_json=report_json)


@app.route("/report/<report_id>/pdf")
def download_pdf(report_id: str):
    """Generate and stream a PDF for a stored report."""
    report_data = REPORT_STORE.get(report_id)
    if not report_data:
        abort(404)

    pdf_path = REPORTS_FOLDER / f"{report_id}.pdf"
    try:
        generate_pdf_report(report_data, str(pdf_path))
        name = report_data.get("name", "report").replace(" ", "_").lower()
        return send_file(
            str(pdf_path),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"dna_report_{name}.pdf",
        )
    except Exception as e:
        logger.exception("PDF generation error")
        return jsonify({"error": f"PDF generation failed: {e}"}), 500


@app.route("/report/<report_id>/html")
def download_html(report_id: str):
    """Generate and stream a standalone HTML report."""
    report_data = REPORT_STORE.get(report_id)
    if not report_data:
        abort(404)

    html_path = REPORTS_FOLDER / f"{report_id}.html"
    try:
        generate_html_report(report_data, str(html_path))
        name = report_data.get("name", "report").replace(" ", "_").lower()
        return send_file(
            str(html_path),
            mimetype="text/html",
            as_attachment=True,
            download_name=f"dna_report_{name}.html",
        )
    except Exception as e:
        logger.exception("HTML export error")
        return jsonify({"error": f"HTML export failed: {e}"}), 500


@app.route("/report/<report_id>/json")
def download_json(report_id: str):
    """Return the raw JSON report data."""
    report_data = REPORT_STORE.get(report_id)
    if not report_data:
        abort(404)
    name = report_data.get("name", "report").replace(" ", "_").lower()
    response = app.response_class(
        response=json.dumps(report_data, indent=2, default=str),
        status=200,
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = f'attachment; filename="dna_report_{name}.json"'
    return response


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "reports_in_memory": len(REPORT_STORE)})


# ── 404 / 500 handlers ───────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    logger.info(f"Starting DNA Report Generator on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
