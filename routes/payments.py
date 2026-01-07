from flask import Blueprint, request, jsonify
from db_models.charges import Charge
from services.charge_service import confirm_payment
from security.auth import require_api_key
from audit.logger import logger
from extensions import limiter


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

    confirm_payment(charge, data.get("value"))

    return jsonify({"message": "Payment confirmed"})
