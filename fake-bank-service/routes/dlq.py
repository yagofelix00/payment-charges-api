from flask import Blueprint, jsonify, request
from dlq.storage import list_failed_webhooks, get_by_event_id, mark_replayed
from services.webhook_dispatcher import send_webhook

dlq_bp = Blueprint("dlq", __name__, url_prefix="/bank/dlq")


@dlq_bp.route("", methods=["GET"])
def dlq_list():
    limit = int(request.args.get("limit", 50))
    items = list_failed_webhooks(limit=limit)
    return jsonify({"count": len(items), "items": items}), 200


@dlq_bp.route("/replay", methods=["POST"])
def dlq_replay_one():
    data = request.get_json() or {}
    event_id = data.get("event_id")
    if not event_id:
        return jsonify({"error": "event_id is required"}), 400

    record = get_by_event_id(event_id)
    if not record:
        return jsonify({"error": "event_id not found in DLQ"}), 404

    ok = send_webhook(url=record["url"], payload=record["payload"])
    if ok:
        mark_replayed(event_id)
        return jsonify({"message": "replayed", "event_id": event_id}), 200

    return jsonify({"message": "replay_failed", "event_id": event_id}), 502
