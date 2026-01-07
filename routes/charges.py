from flask import request, jsonify
from repository.database import db
from db_models.charges import Charge, ChargeStatus
from services.charge_service import check_and_expire
from datetime import datetime, timedelta
import uuid

from audit.logger import logger





@app.route("/charges", methods=["POST"])
def create_charge():
    data = request.get_json()

    if not data or "value" not in data:
        return jsonify({"error": "Value is required"}), 400

    if data["value"] <= 0:
        return jsonify({"error": "Invalid value"}), 400

    charge = Charge(
        value=data["value"],
        status=ChargeStatus.PENDING,
        external_id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )


    db.session.add(charge)
    db.session.commit()
    
    logger.info(
    f"Charge created | charge_id={charge.id} | external_id={charge.external_id} | value={charge.value}"
    )

    return jsonify({"id": charge.id,
                    "external_id": charge.external_id,
                     "status": charge.status}), 201


@app.route("/charges/<int:charge_id>", methods=["GET"])
def get_charge(charge_id):
    charge = Charge.query.get(charge_id)

    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    check_and_expire(charge)

    return jsonify({
        "id": charge.id,
        "value": charge.value,
        "status": charge.status.value,
        "expires_at": charge.expires_at.isoformat()
    })

