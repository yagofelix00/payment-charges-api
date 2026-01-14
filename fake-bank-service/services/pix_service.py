import uuid
import time
from flask import jsonify
from clients.webhook_client import send_webhook

# Simulação de "banco de dados" do banco
BANK_CHARGES = {}

def create_charge(data):
    required = ["external_id", "value", "webhook_url"]
    if not data or not all(k in data for k in required):
        return jsonify({"error": "Invalid payload"}), 400

    BANK_CHARGES[data["external_id"]] = {
        "external_id": data["external_id"],
        "value": data["value"],
        "webhook_url": data["webhook_url"],
        "status": "PENDING"
    }

    return jsonify({"message": "Charge created at bank"}), 201


def pay_charge(data):
    external_id = data.get("external_id")

    charge = BANK_CHARGES.get(external_id)
    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    charge["status"] = "PAID"

    event = {
        "event_id": f"evt_{uuid.uuid4()}",
        "external_id": external_id,
        "value": charge["value"],
        "status": "PAID",
        "timestamp": int(time.time())
    }

    send_webhook(
        url=charge["webhook_url"],
        payload=event
    )

    return jsonify({"message": "Payment processed and webhook sent"}), 200
