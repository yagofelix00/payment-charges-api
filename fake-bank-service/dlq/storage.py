import json
import os
from datetime import datetime
from typing import Dict, List, Optional

DLQ_DIR = os.path.join(os.getcwd(), "dlq_data")
DLQ_FILE = os.path.join(DLQ_DIR, "failed_webhooks.jsonl")


def _ensure_dir():
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
    Append a failed webhook event to a JSON Lines file (one JSON object per line).
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

    with open(DLQ_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_failed_webhooks(limit: int = 50) -> List[Dict]:
    """
    Return last N DLQ events (most recent first).
    """
    if not os.path.exists(DLQ_FILE):
        return []

    with open(DLQ_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    items = [json.loads(line) for line in lines if line.strip()]
    items.reverse()
    return items[:limit]


def _load_all() -> List[Dict]:
    if not os.path.exists(DLQ_FILE):
        return []
    with open(DLQ_FILE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _save_all(records: List[Dict]) -> None:
    _ensure_dir()
    with open(DLQ_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def mark_replayed(event_id: str) -> bool:
    """
    Mark an event as replayed.
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
    records = _load_all()
    for r in records:
        if r.get("event_id") == event_id:
            return r
    return None
