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
  cancelled    →   –   User cancelled the job
  error        →   –   Failed with message

Storage: Redis with 2-hour TTL (falls back to in-memory dict).

Cancellation:
  - cancel(task_id) sets a flag in an in-process dict (_CANCEL_FLAGS).
  - The pipeline thread calls is_cancelled(task_id) between stages;
    if True it raises CancelledError and cleans up.
  - The flag store is in-process only (not Redis) — it only needs to
    live as long as the thread is running, so that's fine.
"""

import os
import json
import time
import uuid
import logging
import threading
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
    "cancelled":    ("Cancelled",                            0),
    "error":        ("Analysis failed",                      0),
}

TASK_TTL = 7200   # 2 hours in Redis


# ── Cancel flag registry (in-process, thread-safe) ────────────────────────────
_CANCEL_FLAGS: dict[str, bool] = {}
_CANCEL_LOCK  = threading.Lock()


class CancelledError(Exception):
    """Raised inside the pipeline thread when the user cancels."""
    pass


def cancel(task_id: str) -> bool:
    """
    Signal a running task to stop.
    Returns True if the flag was set (task existed), False otherwise.
    """
    data = _load(task_id)
    if not data:
        return False
    stage = data.get("stage", "")
    # Can't cancel already-terminal tasks
    if stage in ("done", "cancelled", "error"):
        return False
    with _CANCEL_LOCK:
        _CANCEL_FLAGS[task_id] = True
    # Immediately update stored status so the SSE stream sees it
    data.update({
        "stage":      "cancelled",
        "label":      STAGES["cancelled"][0],
        "pct":        STAGES["cancelled"][1],
        "error":      None,
        "updated_at": time.time(),
    })
    _save(task_id, data)
    return True


def is_cancelled(task_id: str) -> bool:
    """Check whether a cancel has been requested for this task."""
    with _CANCEL_LOCK:
        return _CANCEL_FLAGS.get(task_id, False)


def _clear_cancel_flag(task_id: str) -> None:
    with _CANCEL_LOCK:
        _CANCEL_FLAGS.pop(task_id, None)


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
    """
    Move a task to the given stage.
    Raises CancelledError if a cancel has been requested — call this
    between every major pipeline step so cancellation is responsive.
    """
    # Check cancel flag before advancing
    if is_cancelled(task_id):
        raise CancelledError(f"Task {task_id} was cancelled")

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


def fail(task_id: str, message: str, error_type: str = "error") -> None:
    """Mark a task as failed with an error message."""
    _clear_cancel_flag(task_id)
    data = _load(task_id)
    if not data:
        return
    data.update({
        "stage":      "error",
        "error_type": error_type,
        "label":      "Analysis failed",
        "pct":        0,
        "error":      message,
        "updated_at": time.time(),
    })
    _save(task_id, data)


def complete(task_id: str, report_id: str) -> None:
    """Mark a task as done and attach the final report_id."""
    _clear_cancel_flag(task_id)
    advance(task_id, "done", report_id=report_id)


def get_status(task_id: str) -> Optional[dict]:
    """Return the current task status dict, or None if not found."""
    return _load(task_id)
