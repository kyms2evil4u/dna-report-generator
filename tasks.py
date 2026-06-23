"""
Background Task Tracker — DNA Report Generator

Tracks upload + analysis jobs with granular status stages so the frontend
can show a live progress bar without polling the full pipeline.

Stages (in order):
  queued       →  0%   Task created, not yet started
  uploading    →  10%  File bytes arriving
  upload_done  →  20%  File fully saved to disk
  detecting    →  25%  Detecting file format
  parsing      →  30%  Parsing variant lines
  normalizing  →  45%  Deduplication + normalization
  annotating   →  55%  Calling ClinVar / MyVariant / gnomAD
  categorizing →  80%  Risk scoring + ancestry + PGx
  building     →  90%  Assembling report JSON
  done         → 100%  Report ready — report_id available
  error        →   –   Failed with message

Storage: Redis with 2-hour TTL (falls back to in-memory dict).
"""

import os
import json
import time
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Stage → (label shown to user, % complete)
STAGES = {
    "queued":       ("Queued…",                              0),
    "uploading":    ("Uploading file…",                     10),
    "upload_done":  ("Upload complete, preparing…",         20),
    "detecting":    ("Detecting file format…",              25),
    "parsing":      ("Parsing variants…",                   30),
    "normalizing":  ("Normalizing + deduplicating…",        45),
    "annotating":   ("Annotating with genomic databases…",  55),
    "categorizing": ("Scoring risks & ancestry…",           80),
    "building":     ("Building report…",                    90),
    "done":         ("Complete! Loading report…",          100),
    "error":        ("Analysis failed",                      0),
}

TASK_TTL = 7200   # 2 hours


# ── Storage backend ───────────────────────────────────────────────────────────
_MEMORY: dict = {}   # fallback when Redis is unavailable


def _redis():
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        import redis
        r = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        return r
    except Exception:
        return None


def _key(task_id: str) -> str:
    return f"dna:task:{task_id}"


def _save(task_id: str, data: dict) -> None:
    r = _redis()
    if r:
        try:
            r.setex(_key(task_id), TASK_TTL, json.dumps(data))
            return
        except Exception as e:
            logger.warning(f"Redis task save failed: {e}")
    _MEMORY[task_id] = data


def _load(task_id: str) -> Optional[dict]:
    r = _redis()
    if r:
        try:
            raw = r.get(_key(task_id))
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis task load failed: {e}")
    return _MEMORY.get(task_id)


# ── Public API ────────────────────────────────────────────────────────────────
def create_task(filename: str = "", file_size_mb: float = 0.0) -> str:
    """Create a new task and return its task_id."""
    task_id = str(uuid.uuid4())
    _save(task_id, {
        "task_id":      task_id,
        "stage":        "queued",
        "label":        STAGES["queued"][0],
        "pct":          STAGES["queued"][1],
        "report_id":    None,
        "error":        None,
        "filename":     filename,
        "file_size_mb": round(file_size_mb, 1),
        "created_at":   time.time(),
        "updated_at":   time.time(),
    })
    return task_id


def advance(task_id: str, stage: str, **extra) -> None:
    """Move a task to the given stage, optionally setting extra fields."""
    data = _load(task_id)
    if not data:
        return
    label, pct = STAGES.get(stage, ("Working…", 50))
    data.update({
        "stage":      stage,
        "label":      label,
        "pct":        pct,
        "updated_at": time.time(),
        **extra,
    })
    _save(task_id, data)


def fail(task_id: str, message: str) -> None:
    """Mark a task as failed with an error message."""
    data = _load(task_id)
    if not data:
        return
    data.update({
        "stage":      "error",
        "label":      "Analysis failed",
        "pct":        0,
        "error":      message,
        "updated_at": time.time(),
    })
    _save(task_id, data)


def complete(task_id: str, report_id: str) -> None:
    """Mark a task as done and attach the final report_id."""
    advance(task_id, "done", report_id=report_id)


def get_status(task_id: str) -> Optional[dict]:
    """Return the current task status dict, or None if not found."""
    return _load(task_id)
