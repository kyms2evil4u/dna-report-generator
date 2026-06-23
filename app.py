"""
Flask Web Application — DNA Report Generator
Routes: landing page, file upload/analysis, report viewer, exports

Large-file support:
  - Flask MAX_CONTENT_LENGTH: 2 GB
  - Uploads streamed to disk in 1 MB chunks (never fully buffered in RAM)
  - Size limit configurable via MAX_FILE_SIZE_MB env var (default: 700 MB)
  - Parsers use line-by-line iteration (constant memory regardless of file size)

Progress tracking:
  - /api/analyze returns {task_id} immediately; pipeline runs synchronously
    but emits stage updates into the task store as it progresses.
  - /api/status/<task_id> — poll endpoint (JSON) for current stage/pct/label
  - /api/status/<task_id>/stream — Server-Sent Events stream for real-time
    progress bar without WebSocket overhead
"""

import os
import uuid
import json
import time
import logging
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, request, jsonify, render_template,
    send_file, abort, Response, stream_with_context,
)
from flask_cors import CORS
from werkzeug.utils import secure_filename

import tasks
from parsers import detect_format, parse_23andme, parse_ancestry, parse_myheritage, parse_vcf, normalize_variants
from api import annotate_variants
from analysis import categorize_variants, compute_ancestry, compute_risk_scores, analyze_pharmacogenomics, analyze_traits
from reports import generate_pdf_report, generate_html_report
from data.sample_generator import generate_sample_variants

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32))
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── File size configuration ────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", 700))
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024   # 2 GB hard ceiling
STREAM_CHUNK_SIZE = 1 * 1024 * 1024                          # 1 MB streaming chunks

ALLOWED_EXTENSIONS = {".txt", ".csv", ".vcf", ".gz"}
UPLOAD_FOLDER      = Path(tempfile.gettempdir()) / "dna_uploads"
REPORTS_FOLDER     = Path(tempfile.gettempdir()) / "dna_reports"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)

from store import get_store
REPORT_STORE = get_store()


# ── Helpers ───────────────────────────────────────────────────────────────────
def allowed_file(filename: str) -> bool:
    name = filename.lower()
    if name.endswith(".vcf.gz") or name.endswith(".txt.gz"):
        return True
    return Path(name).suffix in ALLOWED_EXTENSIONS


def stream_save(file_storage, dest_path: Path) -> int:
    """
    Stream a Werkzeug FileStorage to disk in fixed-size chunks.
    Never loads the full file into memory. Returns total bytes written.
    """
    total = 0
    with open(dest_path, "wb") as out:
        while True:
            chunk = file_storage.stream.read(STREAM_CHUNK_SIZE)
            if not chunk:
                break
            out.write(chunk)
            total += len(chunk)
    return total


def parse_file(filepath: str, fmt: str) -> list:
    parsers = {
        "23andme":    parse_23andme,
        "ancestry":   parse_ancestry,
        "myheritage": parse_myheritage,
        "vcf":        parse_vcf,
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
    task_id: str = None,
) -> dict:
    """
    Full analysis pipeline with optional task-stage tracking.
    Each stage calls tasks.advance() so /api/status reflects live progress.
    """
    def _advance(stage, **kw):
        if task_id:
            tasks.advance(task_id, stage, **kw)

    # 1. Detect format
    _advance("detecting")
    fmt = detect_format(filepath)
    logger.info(f"Detected format: {fmt}")
    if fmt == "unknown":
        raise ValueError(
            "Could not detect file format. "
            "Please ensure the file is a valid 23andMe, AncestryDNA, MyHeritage, or VCF export."
        )

    # 2. Parse
    _advance("parsing")
    raw_variants = parse_file(filepath, fmt)
    logger.info(f"Parsed {len(raw_variants):,} raw variants")

    # 3. Normalize
    _advance("normalizing")
    variants = normalize_variants(raw_variants)
    logger.info(f"Normalized to {len(variants):,} clean variants")
    if len(variants) == 0:
        raise ValueError(
            "No valid variants found after normalization. "
            "Check the file format."
        )

    # 4. Annotate
    _advance("annotating")
    annotated = annotate_variants(variants, mode=mode, max_variants=max_variants)

    # 5–9. Score + assemble
    _advance("categorizing")
    categories  = categorize_variants(annotated)
    ancestry    = compute_ancestry(annotated)
    risk_scores = compute_risk_scores(annotated)
    pgx         = analyze_pharmacogenomics(annotated)
    traits      = analyze_traits(annotated)

    _advance("building")
    pathogenic_count = len(categories.get("pathogenic", []))
    report_data = {
        "report_id":    str(uuid.uuid4()),
        "name":         name,
        "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
        "summary": {
            "format":             fmt,
            "mode":               mode,
            "total_variants":     len(variants),
            "annotated_variants": len(annotated),
            "pathogenic_count":   pathogenic_count,
        },
        "ancestry":         ancestry,
        "risk_scores":      risk_scores,
        "pharmacogenomics": pgx,
        "traits":           traits,
        "categories":       categories,
    }

    return report_data


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Accepts a multipart upload.  Returns {task_id} immediately.
    Pipeline runs in a background thread; poll /api/status/<task_id> for progress.
    On completion the status payload includes report_id for redirect.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not allowed_file(f.filename):
        return jsonify({
            "error": "File type not supported. Use .txt, .csv, .vcf, or .vcf.gz"
        }), 400

    name         = request.form.get("name", "User").strip() or "User"
    mode         = request.form.get("mode", "fast")
    max_variants = int(request.form.get("max_variants", 500))

    # Create task immediately so the client can start polling
    filename = secure_filename(f.filename)
    task_id  = tasks.create_task(filename=filename)
    tasks.advance(task_id, "uploading")

    # ── Stream upload to disk ─────────────────────────────────────
    filepath = UPLOAD_FOLDER / f"{uuid.uuid4()}_{filename}"
    try:
        total_bytes = stream_save(f, filepath)
        size_mb = total_bytes / (1024 * 1024)
        logger.info(f"Upload saved: {filename} ({size_mb:.1f} MB)")

        if size_mb > MAX_FILE_SIZE_MB:
            filepath.unlink(missing_ok=True)
            tasks.fail(task_id, (
                f"File too large ({size_mb:.1f} MB). "
                f"Maximum allowed is {MAX_FILE_SIZE_MB} MB. "
                "For whole-genome VCFs over 700 MB, please pre-filter to SNP-only variants."
            ))
            return jsonify({
                "error": (
                    f"File too large ({size_mb:.1f} MB). "
                    f"Maximum allowed is {MAX_FILE_SIZE_MB} MB."
                )
            }), 413

    except Exception as e:
        filepath.unlink(missing_ok=True)
        tasks.fail(task_id, "File upload failed. Please try again.")
        logger.error(f"Upload save failed: {e}")
        return jsonify({"error": "File upload failed. Please try again."}), 500

    tasks.advance(task_id, "upload_done", file_size_mb=round(size_mb, 1))

    # ── Run pipeline in background thread ─────────────────────────
    def _run():
        try:
            report_data = run_full_pipeline(
                str(filepath),
                name=name,
                mode=mode,
                max_variants=max_variants,
                task_id=task_id,
            )
            report_id = report_data["report_id"]
            REPORT_STORE[report_id] = report_data
            tasks.complete(task_id, report_id)
            logger.info(f"Report {report_id} ready for task {task_id} ({size_mb:.1f} MB)")
        except tasks.CancelledError:
            logger.info(f"Task {task_id} was cancelled by user")
            # status already set to 'cancelled' by tasks.cancel()
        except ValueError as e:
            tasks.fail(task_id, str(e))
        except Exception as e:
            logger.exception(f"Pipeline error for task {task_id}")
            tasks.fail(task_id, f"Analysis failed: {str(e)}")
        finally:
            filepath.unlink(missing_ok=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return jsonify({
        "task_id":  task_id,
        "status":   "accepted",
        "filename": filename,
    }), 202


@app.route("/api/status/<task_id>")
def task_status(task_id: str):
    """
    Poll endpoint — returns current task state as JSON.
    Response shape:
      { task_id, stage, label, pct, report_id, error, file_size_mb, updated_at }
    """
    status = tasks.get_status(task_id)
    if not status:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(status)


@app.route("/api/status/<task_id>/stream")
def task_status_stream(task_id: str):
    """
    Server-Sent Events stream for real-time progress.
    The client opens one EventSource; we push updates every 500 ms.
    Stream closes automatically when stage is 'done' or 'error'.

    Event shape:
      data: { task_id, stage, label, pct, report_id, error }
    """
    def _generate():
        last_stage = None
        for _ in range(720):   # max 6 min (720 × 0.5s)
            status = tasks.get_status(task_id)
            if not status:
                yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                return

            # Only push when something changed
            if status["stage"] != last_stage:
                last_stage = status["stage"]
                yield f"data: {json.dumps(status)}\n\n"

            if status["stage"] in ("done", "error", "cancelled"):
                return

            time.sleep(0.5)

        # Timeout safety valve
        yield f"data: {json.dumps({'stage': 'error', 'label': 'Timeout', 'pct': 0})}\n\n"

    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",   # tell Nginx not to buffer SSE
        },
    )

@app.route("/api/cancel/<task_id>", methods=["POST"])
def cancel_task(task_id: str):
    """
    Cancel a running analysis task.
    Sets a flag that the pipeline thread checks between stages;
    the thread cleans up its temp file and exits gracefully.
    Also aborts any pending upload by marking the task cancelled
    so the SSE stream closes and the frontend can react.
    """
    status = tasks.get_status(task_id)
    if not status:
        return jsonify({"error": "Task not found"}), 404

    stage = status.get("stage", "")
    if stage in ("done", "error", "cancelled"):
        return jsonify({
            "cancelled": False,
            "reason": f"Task already in terminal state: {stage}",
        }), 409

    ok = tasks.cancel(task_id)
    if ok:
        logger.info(f"Task {task_id} cancelled (was at stage: {stage})")
        return jsonify({"cancelled": True, "task_id": task_id})
    return jsonify({"cancelled": False, "reason": "Could not cancel task"}), 500


@app.route("/api/sample")
def sample():
    """Generates a report from built-in sample data (no file upload needed)."""
    name = request.args.get("name", "Demo User")
    mode = request.args.get("mode", "fast")

    task_id = tasks.create_task(filename="sample")
    tasks.advance(task_id, "parsing")

    def _run():
        try:
            sample_variants = generate_sample_variants()
            tasks.advance(task_id, "normalizing")
            variants = normalize_variants(sample_variants)
            tasks.advance(task_id, "annotating")
            annotated = annotate_variants(variants, mode=mode, max_variants=100)
            tasks.advance(task_id, "categorizing")
            categories  = categorize_variants(annotated)
            ancestry    = compute_ancestry(annotated)
            risk_scores = compute_risk_scores(annotated)
            pgx         = analyze_pharmacogenomics(annotated)
            traits      = analyze_traits(annotated)
            tasks.advance(task_id, "building")

            report_data = {
                "report_id":    str(uuid.uuid4()),
                "name":         name,
                "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
                "summary": {
                    "format":             "sample",
                    "mode":               mode,
                    "total_variants":     len(variants),
                    "annotated_variants": len(annotated),
                    "pathogenic_count":   len(categories.get("pathogenic", [])),
                },
                "ancestry":         ancestry,
                "risk_scores":      risk_scores,
                "pharmacogenomics": pgx,
                "traits":           traits,
                "categories":       categories,
            }
            report_id = report_data["report_id"]
            REPORT_STORE[report_id] = report_data
            tasks.complete(task_id, report_id)
        except tasks.CancelledError:
            logger.info(f"Sample task {task_id} was cancelled")
        except Exception as e:
            logger.exception("Sample pipeline error")
            tasks.fail(task_id, str(e))

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"task_id": task_id, "status": "accepted"}), 202


@app.route("/report/<report_id>")
def view_report(report_id: str):
    report_data = REPORT_STORE.get(report_id)
    if not report_data:
        abort(404)
    report_json = json.dumps(report_data, default=str)
    return render_template("report.html", report=report_data, report_json=report_json)


@app.route("/report/<report_id>/pdf")
def download_pdf(report_id: str):
    report_data = REPORT_STORE.get(report_id)
    if not report_data:
        abort(404)
    pdf_path = REPORTS_FOLDER / f"{report_id}.pdf"
    try:
        generate_pdf_report(report_data, str(pdf_path))
        name = report_data.get("name", "report").replace(" ", "_").lower()
        return send_file(str(pdf_path), mimetype="application/pdf",
                         as_attachment=True, download_name=f"dna_report_{name}.pdf")
    except Exception as e:
        logger.exception("PDF generation error")
        return jsonify({"error": f"PDF generation failed: {e}"}), 500


@app.route("/report/<report_id>/html")
def download_html(report_id: str):
    report_data = REPORT_STORE.get(report_id)
    if not report_data:
        abort(404)
    html_path = REPORTS_FOLDER / f"{report_id}.html"
    try:
        generate_html_report(report_data, str(html_path))
        name = report_data.get("name", "report").replace(" ", "_").lower()
        return send_file(str(html_path), mimetype="text/html",
                         as_attachment=True, download_name=f"dna_report_{name}.html")
    except Exception as e:
        logger.exception("HTML export error")
        return jsonify({"error": f"HTML export failed: {e}"}), 500


@app.route("/report/<report_id>/json")
def download_json(report_id: str):
    report_data = REPORT_STORE.get(report_id)
    if not report_data:
        abort(404)
    name = report_data.get("name", "report").replace(" ", "_").lower()
    response = app.response_class(
        response=json.dumps(report_data, indent=2, default=str),
        status=200,
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = (
        f'attachment; filename="dna_report_{name}.json"'
    )
    return response


@app.route("/api/health")
def health():
    return jsonify({
        "status":         "ok",
        "reports_stored": REPORT_STORE.count(),
        "max_upload_mb":  MAX_FILE_SIZE_MB,
    })


# ── Error handlers ─────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({
        "error": (
            "File exceeds the 2 GB hard limit. "
            "Please pre-filter your VCF to SNP-only variants before uploading."
        )
    }), 413

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    logger.info(
        f"Starting DNA Report Generator on http://0.0.0.0:{port} "
        f"(max upload: {MAX_FILE_SIZE_MB} MB)"
    )
    app.run(host="0.0.0.0", port=port, debug=debug)
