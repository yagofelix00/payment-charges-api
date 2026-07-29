import json
from datetime import datetime, timedelta

import pytest

from dlq import storage


@pytest.fixture
def temporary_dlq(tmp_path, monkeypatch):
    dlq_dir = tmp_path / "dlq"
    dlq_file = dlq_dir / "failed_webhooks.jsonl"

    monkeypatch.setattr(storage, "DLQ_DIR", str(dlq_dir))
    monkeypatch.setattr(storage, "DLQ_FILE", str(dlq_file))

    return dlq_dir, dlq_file


def _enqueue_sample(event_id="evt_dlq_storage"):
    payload = {
        "event_id": event_id,
        "external_id": "ext_dlq_storage",
        "value": 100.0,
        "status": "PAID",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Timestamp": "1700000000",
        "X-Event-Id": event_id,
    }

    storage.enqueue_failed_webhook(
        url="http://receiver/webhooks/pix",
        payload=payload,
        headers=headers,
        last_status_code=500,
        last_error="temporary failure",
    )

    return payload, headers


def _assert_utc_aware_iso(value):
    parsed = datetime.fromisoformat(value)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


def test_enqueue_failed_webhook_persists_utc_aware_ts_utc(temporary_dlq):
    event_id = "evt_dlq_storage"
    payload, headers = _enqueue_sample(event_id)

    record = storage.get_by_event_id(event_id)

    assert record is not None
    assert record["event_id"] == event_id
    assert record["external_id"] == "ext_dlq_storage"
    assert record["url"] == "http://receiver/webhooks/pix"
    assert record["payload"] == payload
    assert record["headers"] == headers
    assert record["last_status_code"] == 500
    assert record["last_error"] == "temporary failure"
    assert record["replayed"] is False
    assert record["replayed_at_utc"] is None
    _assert_utc_aware_iso(record["ts_utc"])


def test_mark_replayed_persists_utc_aware_replayed_at_utc(temporary_dlq):
    event_id = "evt_dlq_storage_replay"
    _enqueue_sample(event_id)

    result = storage.mark_replayed(event_id)
    record = storage.get_by_event_id(event_id)

    assert result is True
    assert record["replayed"] is True
    assert record["replayed_at_utc"] is not None
    _assert_utc_aware_iso(record["replayed_at_utc"])


def test_mark_replayed_missing_event_does_not_change_existing_record(temporary_dlq):
    event_id = "evt_dlq_storage_existing"
    _enqueue_sample(event_id)

    result = storage.mark_replayed("missing-event")
    record = storage.get_by_event_id(event_id)

    assert result is False
    assert record["replayed"] is False
    assert record["replayed_at_utc"] is None


def test_legacy_naive_timestamp_records_remain_readable(temporary_dlq):
    _, dlq_file = temporary_dlq
    legacy_record = {
        "ts_utc": "2026-07-29T12:34:56.123456",
        "event_id": "evt_legacy",
        "external_id": "ext_legacy",
        "url": "http://receiver/webhooks/pix",
        "payload": {
            "event_id": "evt_legacy",
            "external_id": "ext_legacy",
        },
        "headers": {
            "Content-Type": "application/json",
            "X-Event-Id": "evt_legacy",
        },
        "last_status_code": 500,
        "last_error": "temporary failure",
        "replayed": False,
        "replayed_at_utc": None,
    }
    dlq_file.parent.mkdir(parents=True, exist_ok=True)
    dlq_file.write_text(json.dumps(legacy_record) + "\n", encoding="utf-8")

    items = storage.list_failed_webhooks(limit=10)
    record = storage.get_by_event_id("evt_legacy")

    assert len(items) == 1
    assert record is not None
    assert record["ts_utc"] == "2026-07-29T12:34:56.123456"
    assert record["replayed_at_utc"] is None
