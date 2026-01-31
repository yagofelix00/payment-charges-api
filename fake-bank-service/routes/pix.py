from flask import Blueprint, request, jsonify
from services.webhook_dispatcher import send_webhook
import uuid

pix_bp = Blueprint("pix", __name__, url_prefix="/bank/pix")

# In-memory store used only for simulation (no persistence by design).
# In a real bank/PSP, this would be a database or internal ledger.
BANK_CHARGES = {}


@pix_bp.route("/charges", methods=["POST"])
def create_pix_charge():
    """
    Registers a charge in the fake bank.

    This endpoint simulates the "bank side" receiving a charge request
    from an external payment system and storing minimal state needed
    to later trigger the PIX payment + webhook.
    """
    data = request.get_json()

    external_id = data.get("external_id")
    value = data.get("value")
    webhook_url = data.get("webhook_url")

    if not external_id or not value or not webhook_url:
        return jsonify({"error": "Invalid payload"}), 400

    BANK_CHARGES[external_id] = {
        "external_id": external_id,
        "value": value,
        "webhook_url": webhook_url,
        "status": "PENDING"
    }

    return jsonify({
        "message": "Charge registered in bank",
        "external_id": external_id
    }), 201


@pix_bp.route("/pay", methods=["POST"])
def process_pix_payment():
    """
    Simulates a PIX payment settlement and triggers the webhook callback.

    The webhook delivery itself is handled by the dispatcher (retry/backoff/DLQ),
    keeping this route focused on orchestrating the simulated payment event.
    """
    data = request.get_json()
    external_id = data.get("external_id")

    if not external_id:
        return jsonify({"error": "Invalid payload"}), 400

    charge = BANK_CHARGES.get(external_id)
    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    # Event ID is the idempotency key for webhook processing on the receiver side.
    event_id = f"evt_{uuid.uuid4()}"

    payload = {
        "event_id": event_id,
        "external_id": external_id,
        "value": charge["value"],
        "status": "PAID"
    }

    # Trigger webhook (retry/backoff + DLQ on permanent failure).
    send_webhook(
        url=charge["webhook_url"],
        payload=payload
    )

    # Update the simulated bank state after dispatch attempt.
    # (In real systems you'd also track settlement timestamps, reconciliation, etc.)
    charge["status"] = "PAID"

    return jsonify({
        "message": "PIX processed by bank",
        "event_id": event_id
    }), 200



