from flask import Blueprint, request, jsonify
from db_models.charges import Charge
from services.charge_service import confirm_payment
from security.auth import require_api_key
from audit.logger import logger
from extensions import limiter
from db_models.charges import Charge, ChargeStatus
from repository.database import db
from infrastructure.redis_client import redis_client

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("/external/payments", methods=["POST"])
@limiter.limit("5 per minute")
@require_api_key
def external_payment():
    data = request.get_json()
    
    if not data or "external_id" not in data or "value" not in data:
        return jsonify({"error": "Invalid payload"}), 400
    
    charge = Charge.query.filter_by(
        external_id=data.get("external_id")
    ).first()

    if not charge:
        return jsonify({"error": "Invalid external_id"}), 400
    
    ttl_key = f"charge:ttl:{charge.id}"

    # 🔥 Redis manda na expiração
    if not redis_client.exists(ttl_key):
        if charge.status == ChargeStatus.PENDING:
            charge.status = ChargeStatus.EXPIRED
            db.session.commit()

        logger.warning(
            f"Payment attempt on expired charge | charge_id={charge.id}"
        )

        return jsonify({"error": "Charge expired"}), 400
    
    confirm_payment(charge, data.get("value"))

    logger.info(
        f"Payment confirmed | charge_id={charge.id} | external_id={charge.external_id}"
    )

    return jsonify({"message": "Payment confirmed"})
