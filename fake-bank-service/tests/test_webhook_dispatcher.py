import hashlib
import hmac
import json

from config import Config
from dlq import storage
from services import webhook_dispatcher


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


def _expected_signature(secret, timestamp, body):
    digest = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _redirect_dlq_to_tmp_path(monkeypatch, tmp_path):
    dlq_dir = tmp_path / "dlq_data"
    dlq_file = dlq_dir / "failed_webhooks.jsonl"
    monkeypatch.setattr(storage, "DLQ_DIR", str(dlq_dir))
    monkeypatch.setattr(storage, "DLQ_FILE", str(dlq_file))
    return dlq_file


def test_send_webhook_recalculates_timestamp_and_signature_per_retry(monkeypatch):
    monkeypatch.setattr(Config, "WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setattr(webhook_dispatcher, "get_request_id", lambda: "req-test")
    monkeypatch.setattr(webhook_dispatcher.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(webhook_dispatcher.random, "uniform", lambda start, end: 0)

    timestamps = iter([1700000000, 1700000001])
    monkeypatch.setattr(webhook_dispatcher.time, "time", lambda: next(timestamps))

    calls = []

    def fake_post(url, data, headers, timeout):
        calls.append({
            "url": url,
            "data": data,
            "headers": dict(headers),
            "timeout": timeout,
        })
        return FakeResponse(500 if len(calls) == 1 else 200, "temporary failure")

    monkeypatch.setattr(webhook_dispatcher.requests, "post", fake_post)

    payload = {
        "event_id": "evt_retry_signature",
        "external_id": "ext-retry-signature-ação",
        "value": 100.0,
        "status": "PAID",
    }

    delivered = webhook_dispatcher.send_webhook(
        "http://receiver/webhooks/pix",
        payload,
        max_retries=2,
    )

    expected_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    expected_body_bytes = expected_body.encode("utf-8")
    assert delivered is True
    assert [call["data"] for call in calls] == [
        expected_body_bytes,
        expected_body_bytes,
    ]
    assert [call["headers"]["X-Timestamp"] for call in calls] == ["1700000000", "1700000001"]
    assert calls[0]["headers"]["X-Signature"] == _expected_signature(
        "test-webhook-secret",
        "1700000000",
        expected_body,
    )
    assert calls[1]["headers"]["X-Signature"] == _expected_signature(
        "test-webhook-secret",
        "1700000001",
        expected_body,
    )
    assert calls[0]["headers"]["X-Signature"] != calls[1]["headers"]["X-Signature"]
    assert calls[0]["headers"]["X-Event-Id"] == "evt_retry_signature"
    assert calls[1]["headers"]["X-Event-Id"] == "evt_retry_signature"
    assert calls[0]["headers"]["X-Request-Id"] == "req-test"


def test_failed_webhook_dlq_persists_last_headers_without_signature(monkeypatch):
    monkeypatch.setattr(Config, "WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setattr(webhook_dispatcher, "get_request_id", lambda: "req-test")
    monkeypatch.setattr(webhook_dispatcher.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(webhook_dispatcher.time, "time", lambda: 1700000000)

    def fake_post(url, data, headers, timeout):
        return FakeResponse(500, "temporary failure")

    enqueued = {}

    def fake_enqueue_failed_webhook(**kwargs):
        enqueued.update(kwargs)

    monkeypatch.setattr(webhook_dispatcher.requests, "post", fake_post)
    monkeypatch.setattr(webhook_dispatcher, "enqueue_failed_webhook", fake_enqueue_failed_webhook)

    payload = {
        "event_id": "evt_dlq_headers",
        "external_id": "ext-dlq-headers",
        "value": 100.0,
        "status": "PAID",
    }

    delivered = webhook_dispatcher.send_webhook(
        "http://receiver/webhooks/pix",
        payload,
        max_retries=1,
    )

    assert delivered is False
    assert enqueued["payload"] == payload
    assert enqueued["headers"]["X-Timestamp"] == "1700000000"
    assert enqueued["headers"]["X-Event-Id"] == "evt_dlq_headers"
    assert "X-Signature" not in enqueued["headers"]


def test_failed_webhook_after_all_retries_persists_to_temp_dlq(monkeypatch, tmp_path):
    dlq_file = _redirect_dlq_to_tmp_path(monkeypatch, tmp_path)
    monkeypatch.setattr(Config, "WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setattr(webhook_dispatcher, "get_request_id", lambda: "req-test")
    monkeypatch.setattr(webhook_dispatcher.random, "uniform", lambda start, end: 0)
    monkeypatch.setattr(webhook_dispatcher.time, "time", lambda: 1700000000)

    sleep_calls = []
    post_calls = []

    monkeypatch.setattr(webhook_dispatcher.time, "sleep", sleep_calls.append)

    def fake_post(url, data, headers, timeout):
        post_calls.append({
            "url": url,
            "data": data,
            "headers": dict(headers),
            "timeout": timeout,
        })
        return FakeResponse(500, "temporary failure")

    monkeypatch.setattr(webhook_dispatcher.requests, "post", fake_post)

    url = "http://receiver/webhooks/pix"
    payload = {
        "event_id": "evt_dlq_persisted",
        "external_id": "ext-dlq-persisted",
        "value": 100.0,
        "status": "PAID",
    }

    delivered = webhook_dispatcher.send_webhook(
        url,
        payload,
        max_retries=5,
        initial_delay_seconds=1.0,
        backoff_multiplier=2.0,
        max_delay_seconds=30.0,
    )

    assert delivered is False
    assert len(post_calls) == 5
    assert sleep_calls == [1.0, 2.0, 4.0, 8.0]

    assert dlq_file.exists()
    lines = [line for line in dlq_file.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["url"] == url
    assert record["payload"] == payload
    assert record["event_id"] == "evt_dlq_persisted"
    assert record["external_id"] == "ext-dlq-persisted"
    assert record["headers"]["Content-Type"] == "application/json"
    assert record["headers"]["X-Timestamp"] == "1700000000"
    assert record["headers"]["X-Event-Id"] == "evt_dlq_persisted"
    assert record["headers"]["X-Request-Id"] == "req-test"
    assert "X-Signature" not in record["headers"]
    assert record["last_status_code"] == 500
    assert record["last_error"] is None
    assert record["replayed"] is False
    assert record["replayed_at_utc"] is None


def test_send_webhook_success_first_attempt_does_not_sleep_or_write_dlq(monkeypatch, tmp_path):
    dlq_file = _redirect_dlq_to_tmp_path(monkeypatch, tmp_path)
    monkeypatch.setattr(Config, "WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setattr(webhook_dispatcher, "get_request_id", lambda: "req-test")
    monkeypatch.setattr(webhook_dispatcher.random, "uniform", lambda start, end: 0)
    monkeypatch.setattr(webhook_dispatcher.time, "time", lambda: 1700000000)

    sleep_calls = []
    post_calls = []

    monkeypatch.setattr(webhook_dispatcher.time, "sleep", sleep_calls.append)

    def fake_post(url, data, headers, timeout):
        post_calls.append({
            "url": url,
            "data": data,
            "headers": dict(headers),
            "timeout": timeout,
        })
        return FakeResponse(200, "ok")

    monkeypatch.setattr(webhook_dispatcher.requests, "post", fake_post)

    delivered = webhook_dispatcher.send_webhook(
        "http://receiver/webhooks/pix",
        {
            "event_id": "evt_success_first",
            "external_id": "ext-success-first",
            "value": 100.0,
            "status": "PAID",
        },
    )

    assert delivered is True
    assert len(post_calls) == 1
    assert sleep_calls == []
    assert not dlq_file.exists()


def test_send_webhook_success_after_retry_does_not_write_dlq(monkeypatch, tmp_path):
    dlq_file = _redirect_dlq_to_tmp_path(monkeypatch, tmp_path)
    monkeypatch.setattr(Config, "WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setattr(webhook_dispatcher, "get_request_id", lambda: "req-test")
    monkeypatch.setattr(webhook_dispatcher.random, "uniform", lambda start, end: 0)
    monkeypatch.setattr(webhook_dispatcher.time, "time", lambda: 1700000000)

    sleep_calls = []
    post_calls = []
    responses = [500, 500, 200]

    monkeypatch.setattr(webhook_dispatcher.time, "sleep", sleep_calls.append)

    def fake_post(url, data, headers, timeout):
        post_calls.append({
            "url": url,
            "data": data,
            "headers": dict(headers),
            "timeout": timeout,
        })
        return FakeResponse(responses[len(post_calls) - 1], "temporary failure")

    monkeypatch.setattr(webhook_dispatcher.requests, "post", fake_post)

    delivered = webhook_dispatcher.send_webhook(
        "http://receiver/webhooks/pix",
        {
            "event_id": "evt_success_after_retry",
            "external_id": "ext-success-after-retry",
            "value": 100.0,
            "status": "PAID",
        },
    )

    assert delivered is True
    assert len(post_calls) == 3
    assert sleep_calls == [1.0, 2.0]
    assert not dlq_file.exists()
