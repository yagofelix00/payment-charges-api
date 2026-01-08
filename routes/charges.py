from flask import Blueprint, request, jsonify
from repository.database import db
from db_models.charges import Charge, ChargeStatus
from services.charge_service import check_and_expire
from datetime import datetime, timedelta
import uuid
from infrastructure.redis_client import redis_client
import json

from audit.logger import logger

charges_bp = Blueprint("charges", __name__)

@charges_bp.route("/charges", methods=["POST"])
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


@charges_bp.route("/charges/<int:charge_id>", methods=["GET"])
def get_charge(charge_id):
    cache_key = f"charge:{charge_id}"

    cached = redis_client.get(cache_key)
    if cached:
        return jsonify(json.loads(cached))
    
    charge = Charge.query.get(charge_id)
    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    check_and_expire(charge)

    response = {
        "id": charge.id,
        "value": charge.value,
        "status": charge.status,
        "expires_at": charge.expires_at.isoformat()
    }

    redis_client.setex(
        cache_key,
        60,  # cache por 60s
        json.dumps(response)
    )

    return jsonify(response)

