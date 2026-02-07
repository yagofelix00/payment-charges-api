from flask import Blueprint, request, jsonify
from repository.database import db
from db_models.charges import Charge, ChargeStatus
from datetime import datetime
from infrastructure.redis_client import redis_client
from security.idempotency import idempotent
from audit.logger import logger
from security.webhook_signature import require_webhook_signature
from decimal import Decimal, InvalidOperation

# Blueprint responsible for handling incoming payment webhooks
webhooks_bp = Blueprint("webhooks", __name__)

def to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None

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
    data = request.get_json(silent=True)
    
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    external_id = data.get("external_id")
    value = data.get("value")
    status = data.get("status")

    # Centralized safety guard: catch unexpected exceptions and ensure
    # we return a controlled 500 while logging the full stack trace.
    try:
        # 🧾 1. Extrai payload e valida campos mínimos
        if not external_id or not value or not status:
            return jsonify({"error": "Invalid payload"}), 400

        # 📤 2. Ignora notificações que não representam pagamento concluído
        if status != "PAID":
            return jsonify({"message": "Ignored"}), 200

        # 🔍 3. Busca cobrança
        charge = Charge.query.filter_by(external_id=external_id).first()
        if not charge:
            logger.error(f"Charge not found | external_id={external_id}")
            return jsonify({"error": "Charge not found"}), 404

        # 🔐 4. Regras de negócio: apenas cobranças pendentes podem ser processadas
        if charge.status != ChargeStatus.PENDING:
            logger.warning(f"Ignored webhook for non-pending charge | id={charge.id}")
            return jsonify({"message": "Charge already processed"}), 200

        # 🔑 Chave Redis usada para controlar TTL/validade da cobrança.
        ttl_key = f"charge:ttl:{external_id}"

        # Redis é a fonte da verdade para validar se a cobrança ainda pode
        # ser confirmada por webhook. Tratamos erros de conexão com Redis
        # de forma explícita: se ocorrer um erro, respondemos 503.
        try:
            ttl_exists = redis_client.exists(ttl_key)
        except Exception:
            logger.exception(f"Redis check failed for ttl_key={ttl_key}")
            return jsonify({"error": "Service unavailable"}), 503

        if not ttl_exists:
            try:
                charge.status = ChargeStatus.EXPIRED
                db.session.commit()
            except Exception:
                db.session.rollback()
                logger.exception(f"Failed to mark charge expired | id={charge.id}")
                return jsonify({"error": "Internal server error"}), 500

            logger.warning(
                f"Webhook received for expired charge | charge_id={charge.id}"
            )
            return jsonify({"error": "Charge expired"}), 400
      
        # ...
        value_dec = to_decimal(value)
        charge_value_dec = to_decimal(charge.value)

        if value_dec is None:
            return jsonify({"error": "Invalid value type"}), 400

        if value_dec != charge_value_dec:
            logger.warning(f"Invalid value on webhook | charge_id={charge.id} | got={value_dec} expected={charge_value_dec}")
            return jsonify({"error": "Invalid value"}), 400


        # Atualiza o estado do charge para PAID e registra o timestamp UTC.
        charge.status = ChargeStatus.PAID
        charge.paid_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception(f"Failed to commit payment for charge | id={charge.id}")
            return jsonify({"error": "Internal server error"}), 500

        # Log informativo para auditoria / monitoramento.
        logger.info(
            f"Payment confirmed via webhook", 
            extra={"charge_id": charge.id, "external_id": external_id}
        )

        return jsonify({"message": "Payment confirmed"}), 200

    except Exception:
        # Fallback: log completo e resposta genérica. Não vaza detalhes.
        logger.exception("Unhandled error processing PIX webhook")
        return jsonify({"error": "Internal server error"}), 500


