import json

import pytest
from flask import Flask

from dlq import storage
from routes import dlq as dlq_routes


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(dlq_routes.dlq_bp)
    return app.test_client()


@pytest.fixture
def temporary_dlq(monkeypatch, tmp_path):
    dlq_dir = tmp_path / "dlq_data"
    dlq_file = dlq_dir / "failed_webhooks.jsonl"

    monkeypatch.setattr(storage, "DLQ_DIR", str(dlq_dir))
    monkeypatch.setattr(storage, "DLQ_FILE", str(dlq_file))

    return dlq_dir, dlq_file


def _write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_list_dlq_returns_empty_response_when_file_does_not_exist(
    client,
    temporary_dlq,
):
    dlq_dir, dlq_file = temporary_dlq

    response = client.get("/bank/dlq")

    assert response.status_code == 200
    assert response.is_json
    assert response.content_type.startswith("application/json")
    assert response.get_json() == {"count": 0, "items": []}
    assert not dlq_file.exists()
    assert not dlq_dir.exists()


def test_list_dlq_uses_default_limit_and_returns_newest_first(
    client,
    temporary_dlq,
):
    records = [
        {
            "event_id": f"evt-{index}",
            "external_id": f"ext-{index}",
            "position": index,
        }
        for index in range(51)
    ]
    _, dlq_file = temporary_dlq
    _write_jsonl(dlq_file, records)

    response = client.get("/bank/dlq")
    payload = response.get_json()
    expected_items = list(reversed(records))[:50]

    assert response.status_code == 200
    assert response.is_json
    assert payload["count"] == 50
    assert len(payload["items"]) == 50
    assert payload["items"][0] == records[50]
    assert payload["items"][-1] == records[1]
    assert records[0] not in payload["items"]
    assert payload["items"] == expected_items


def test_list_dlq_respects_limit_query_parameter(
    client,
    temporary_dlq,
):
    records = [
        {"event_id": "evt-0", "external_id": "ext-0", "position": 0},
        {"event_id": "evt-1", "external_id": "ext-1", "position": 1},
        {"event_id": "evt-2", "external_id": "ext-2", "position": 2},
    ]
    _, dlq_file = temporary_dlq
    _write_jsonl(dlq_file, records)

    response = client.get("/bank/dlq?limit=1")

    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == {
        "count": 1,
        "items": [records[-1]],
    }


def test_list_dlq_accepts_maximum_limit(client, temporary_dlq):
    records = [
        {
            "event_id": f"evt-{index}",
            "external_id": f"ext-{index}",
            "position": index,
        }
        for index in range(101)
    ]
    _, dlq_file = temporary_dlq
    _write_jsonl(dlq_file, records)

    response = client.get("/bank/dlq?limit=100")
    payload = response.get_json()

    assert response.status_code == 200
    assert response.is_json
    assert payload["count"] == 100
    assert len(payload["items"]) == 100
    assert payload["items"][0] == records[100]
    assert records[0] not in payload["items"]


@pytest.mark.parametrize(
    "raw_limit",
    [
        "0",
        "-1",
        "abc",
        "1.5",
        "101",
        "",
        " 1",
        "1 ",
        "+1",
        "9" * 5000,
        "１２",
    ],
)
def test_list_dlq_rejects_invalid_limit(client, monkeypatch, raw_limit):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("storage should not be called")

    monkeypatch.setattr(
        dlq_routes,
        "list_failed_webhooks",
        fail_if_called,
    )

    response = client.get(
        "/bank/dlq",
        query_string={"limit": raw_limit},
    )

    assert response.status_code == 400
    assert response.is_json
    assert response.get_json() == {"error": "Invalid limit"}


def test_list_dlq_rejects_repeated_limit(client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("storage should not be called")

    monkeypatch.setattr(
        dlq_routes,
        "list_failed_webhooks",
        fail_if_called,
    )

    response = client.get(
        "/bank/dlq",
        query_string=[
            ("limit", "1"),
            ("limit", "2"),
        ],
    )

    assert response.status_code == 400
    assert response.is_json
    assert response.get_json() == {"error": "Invalid limit"}


def test_legacy_duplicated_dlq_route_returns_404(client):
    response = client.get("/bank/dlq/dlq")

    assert response.status_code == 404
