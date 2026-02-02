import json
import os
from datetime import datetime
from typing import Dict, List, Optional

# DLQ storage is file-based (JSON Lines) on purpose:
# - simple to operate
# - append-only
# - human-readable for audits
DLQ_DIR = os.path.join(os.getcwd(), "dlq_data")
DLQ_FILE = os.path.join(DLQ_DIR, "failed_webhooks.jsonl")


def _ensure_dir():
    # Ensure DLQ directory exists before any write operation
    os.makedirs(DLQ_DIR, exist_ok=True)


def enqueue_failed_webhook(
    *,
    url: str,
    payload: Dict,
    headers: Dict,
    last_status_code: Optional[int] = None,
    last_error: Optional[str] = None,
) -> None:
    """
    Persist a definitively failed webhook event to the Dead Letter Queue.

    This function is called only after all retry attempts are exhausted,
    guaranteeing that no delivery failures are silently lost.
    """
    _ensure_dir()

    record = {
        "ts_utc": datetime.utcnow().isoformat(),
        "event_id": payload.get("event_id"),
        "external_id": payload.get("external_id"),
        "url": url,
        "payload": payload,
        "headers": headers,
        "last_status_code": last_status_code,
        "last_error": last_error,
        "replayed": False,
        "replayed_at_utc": None,
    }

    # Append-only write to preserve failure history and ordering
    with open(DLQ_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_failed_webhooks(limit: int = 50) -> List[Dict]:
    """
    Return the most recent failed webhook events.

    Ordering is reversed to prioritize operational visibility
    of the latest failures.
    """
    if not os.path.exists(DLQ_FILE):
        return []

    with open(DLQ_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    items = [json.loads(line) for line in lines if line.strip()]
    items.reverse()
    return items[:limit]


def _load_all() -> List[Dict]:
    # Internal helper to load the entire DLQ file into memory.
    # Acceptable here due to expected low volume (simulation scope).
    if not os.path.exists(DLQ_FILE):
        return []
    with open(DLQ_FILE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _save_all(records: List[Dict]) -> None:
    # Rewrite file only for state transitions (e.g., mark as replayed)
    _ensure_dir()
    with open(DLQ_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def mark_replayed(event_id: str) -> bool:
    """
    Mark a DLQ event as successfully replayed.

    This is used for auditability and to prevent accidental
    repeated reprocessing of the same event.
    """
    records = _load_all()
    changed = False

    for r in records:
        if r.get("event_id") == event_id:
            r["replayed"] = True
            r["replayed_at_utc"] = datetime.utcnow().isoformat()
            changed = True

    if changed:
        _save_all(records)

    return changed


def get_by_event_id(event_id: str) -> Optional[Dict]:
    """
    Retrieve a DLQ record by event_id.

    Used mainly for targeted replay operations.
    """
    records = _load_all()
    for r in records:
        if r.get("event_id") == event_id:
            return r
    return None

