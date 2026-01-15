from flask import Blueprint, request, jsonify
from services.webhook_dispatcher import send_webhook
import uuid

pix_bp = Blueprint("pix", __name__, url_prefix="/bank/pix")

# Simulated in-memory storage for bank charges
BANK_CHARGES = {}


@pix_bp.route("/charges", methods=["POST"])
def create_pix_charge():
    """
    Register a PIX charge in the fake bank system.
    This simulates the bank receiving a charge request.
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
    Simulate PIX payment processing and trigger webhook.
    """
    data = request.get_json()

    external_id = data.get("external_id")

    if not external_id:
        return jsonify({"error": "Invalid payload"}), 400

    charge = BANK_CHARGES.get(external_id)
    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    event_id = f"evt_{uuid.uuid4()}"

    payload = {
        "event_id": event_id,
        "external_id": external_id,
        "value": charge["value"],
        "status": "PAID"
    }

    # Trigger webhook with retry + backoff
    send_webhook(
        url=charge["webhook_url"],
        payload=payload
    )

    charge["status"] = "PAID"

    return jsonify({
        "message": "PIX processed by bank",
        "event_id": event_id
    }), 200


