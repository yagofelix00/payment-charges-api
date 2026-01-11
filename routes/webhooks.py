from flask import Blueprint, request, jsonify
from repository.database import db
from db_models.charges import Charge, ChargeStatus
from datetime import datetime

from security.auth import require_api_key
from security.idempotency import idempotent
from audit.logger import logger

webhooks_bp = Blueprint("webhooks", __name__)

@webhooks_bp.route("/webhooks/pix", methods=["POST"])
@require_api_key
@idempotent(ttl=300)
def pix_webhook():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid payload"}), 400

    external_id = data.get("external_id")
    value = data.get("value")
    status = data.get("status")

    if not external_id or not value or not status:
        return jsonify({"error": "Missing fields"}), 400

    charge = Charge.query.filter_by(external_id=external_id).first()

    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    # 🔒 Regra CRÍTICA
    if status not in ["PAID", "EXPIRED"]:
        return jsonify({"error": "Invalid status"}), 400

    if charge.status != ChargeStatus.PENDING:
        return jsonify({"message": "Charge already processed"}), 200

    if value != charge.value:
        logger.warning(f"Webhook value mismatch | external_id={external_id}")
        return jsonify({"error": "Invalid value"}), 400

    if status == "PAID":
        charge.status = ChargeStatus.PAID
        charge.paid_at = datetime.utcnow()

    elif status == "EXPIRED":
        charge.status = ChargeStatus.EXPIRED

    db.session.commit()

    logger.info(
        f"PIX webhook processed | external_id={external_id} | status={charge.status}"
    )

    return jsonify({"message": "Webhook processed"}), 200
