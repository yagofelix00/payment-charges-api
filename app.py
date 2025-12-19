from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)

charges = []  # memória por enquanto

@app.route("/charges", methods=["POST"])
def create_charge():
    data = request.get_json()

    if not data or "value" not in data:
        return jsonify({"error": "Value is required"}), 400

    if data["value"] <= 0:
        return jsonify({"error": "Invalid value"}), 400

    charge = {
        "id": len(charges) + 1,
        "value": data["value"],
        "status": "PENDING",
        "external_id": str(uuid.uuid4()),
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(minutes=30)
    }

    charges.append(charge)

    return jsonify(charge), 201
   

@app.route("/charges/<int:charge_id>", methods=["GET"])
def get_charge(charge_id):
    charge = next((c for c in charges if c["id"] == charge_id), None)

    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    return jsonify(charge)


@app.route("/external/payments", methods=["POST"])
def external_payment():
    data = request.get_json()

    charge = next(
        (c for c in charges if c["external_id"] == data.get("external_id")),
        None
    )

    if not charge:
        return jsonify({"error": "Invalid external_id"}), 400

    if data["value"] != charge["value"]:
        return jsonify({"error": "Invalid value"}), 400

    if datetime.now() > charge["expires_at"]:
        charge["status"] = "EXPIRED"
        return jsonify({"error": "Charge expired"}), 400

    # Simula webhook
    confirm_payment(charge)

    return jsonify({"message": "Payment processed"})

def confirm_payment(charge):
    if charge["status"] != "PENDING":
        return

    charge["status"] = "PAID"
    charge["paid_at"] = datetime.now()
