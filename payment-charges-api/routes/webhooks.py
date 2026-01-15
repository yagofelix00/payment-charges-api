from flask import Blueprint, request, jsonify
from repository.database import db
from db_models.charges import Charge, ChargeStatus
from datetime import datetime
from infrastructure.redis_client import redis_client
from security.idempotency import idempotent
from audit.logger import logger
from security.webhook_signature import require_webhook_signature


# Blueprint responsible for handling incoming payment webhooks
webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("/webhooks/pix", methods=["POST"])
@require_webhook_signature
@idempotent(ttl=300)
def pix_webhook():
    """
    PIX payment webhook endpoint.

    This endpoint is called by the bank (or fake bank service) to notify
    about payment status changes.

    Responsibilities:
    - Validate webhook authenticity (HMAC signature)
    - Prevent duplicated event processing (idempotency)
    - Validate payload integrity
    - Ensure charge is still valid using Redis TTL
    - Update payment status in the database
    """

    # Parse incoming JSON payload
    data = request.get_json()

    external_id = data.get("external_id")
    value = data.get("value")
    status = data.get("status")

    # Basic payload validation
    if not external_id or not value or not status:
        return jsonify({"error": "Invalid payload"}), 400

    # Ignore events that are not payment confirmations
    if status != "PAID":
        return jsonify({"message": "Ignored"}), 200

    # Retrieve charge using external identifier
    charge = Charge.query.filter_by(external_id=external_id).first()
    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    # Redis key that represents charge expiration (source of truth)
    ttl_key = f"charge:ttl:{external_id}"

    # If the TTL key does not exist, the charge has expired
    if not redis_client.exists(ttl_key):
        charge.status = ChargeStatus.EXPIRED
        db.session.commit()

        logger.warning(
            f"Webhook received for expired charge | charge_id={charge.id}"
        )
        return jsonify({"error": "Charge expired"}), 400

    # Validate payment amount to avoid tampering or inconsistencies
    if value != charge.value:
        logger.warning(
            f"Invalid value on webhook | charge_id={charge.id}"
        )
        return jsonify({"error": "Invalid value"}), 400

    # Mark charge as paid
    charge.status = ChargeStatus.PAID
    charge.paid_at = datetime.utcnow()
    db.session.commit()

    logger.info(
        f"Payment confirmed via webhook | charge_id={charge.id}"
    )

    return jsonify({"message": "Payment confirmed"}), 200


