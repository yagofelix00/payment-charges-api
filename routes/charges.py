from flask import Blueprint, request, jsonify
from repository.database import db
from db_models.charges import Charge, ChargeStatus
from datetime import datetime
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
    )


    db.session.add(charge)
    db.session.commit()

    # 🔥 Redis controla a expiração
    redis_client.setex(
        f"charge:ttl:{charge.external_id}",
        1800,  # 30 minutos
        "PENDING"
    )
    
    logger.info(
    f"Charge created | charge_id={charge.id} | external_id={charge.external_id}"
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

    ttl_key = f"charge:ttl:{charge.external_id}"
    
    if not redis_client.exists(ttl_key):
        if charge.status == ChargeStatus.PENDING:
            charge.status = ChargeStatus.EXPIRED
            db.session.commit()
            redis_client.delete(cache_key)

    response = {
        "id": charge.id,
        "value": charge.value,
        "status": charge.status,
    }

    redis_client.setex(
        cache_key,
        60,  # cache por 60s
        json.dumps(response)
    )

    return jsonify(response)

