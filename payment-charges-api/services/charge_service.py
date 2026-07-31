from datetime import datetime
import uuid
from repository.database import db
from db_models.charges import Charge, ChargeStatus
from exceptions.charge_exceptions import (
    ChargeNotPayable,
    InvalidChargeValue
)
from audit.logger import logger
from infrastructure.redis_client import redis_client
from services.money import InvalidMoneyValue, parse_money


def create_charge(value):

    try:
        money_value = parse_money(value)
    except InvalidMoneyValue:
        raise InvalidChargeValue("Invalid value")

    # Charges start as PENDING. Payment confirmation must happen asynchronously via webhook.
    charge = Charge(
        value=money_value,
        status=ChargeStatus.PENDING,
        external_id=str(uuid.uuid4()),  # Public identifier shared with the bank / external systems
        created_at=datetime.utcnow(),
    )

    db.session.add(charge)
    db.session.commit()

    # Redis TTL acts as the "source of truth" for charge expiration:
    # - If the TTL key expires, a PENDING charge becomes EXPIRED on next read (lazy expiration).
    # - This avoids periodic cron jobs and keeps expiration logic consistent across services.
    redis_client.setex(
        f"charge:ttl:{charge.external_id}",
        1800,  # 30 minutes
        "PENDING",
    )

    # Structured log: keeps operational traceability (request_id injected by LoggerAdapter)
    logger.info(
        f"Charge created | charge_id={charge.id} | external_id={charge.external_id}"
    )

    return charge


def confirm_payment(charge, value):

    if charge.status != ChargeStatus.PENDING:
        logger.warning(
            f"Invalid payment attempt | charge_id={charge.id} | status={charge.status}"
        )
        raise ChargeNotPayable("Charge not payable")

    try:
        money_value = parse_money(value)
    except InvalidMoneyValue:
        raise InvalidChargeValue("Invalid value")

    if charge.value != money_value:
        logger.warning(
            f"Payment value mismatch | charge_id={charge.id} | expected={charge.value} | received={money_value}"
        )
        raise InvalidChargeValue("Invalid value")

    charge.status = ChargeStatus.PAID
    charge.paid_at = datetime.utcnow()
    db.session.commit()

    # Limpa TODOS os caches
    cache_key = f"charge:{charge.id}"
    try:
        redis_client.delete(cache_key)
    except Exception:
        logger.exception(
            "Failed to delete legacy charge cache after payment confirmation",
            extra={
                "charge_id": charge.id,
                "external_id": charge.external_id,
                "redis_key": cache_key,
                "cleanup_operation": "delete_charge_cache",
            },
        )

    ttl_key = f"charge:ttl:{charge.external_id}"
    try:
        redis_client.delete(ttl_key)
    except Exception:
        logger.exception(
            "Failed to delete legacy charge TTL after payment confirmation",
            extra={
                "charge_id": charge.id,
                "external_id": charge.external_id,
                "redis_key": ttl_key,
                "cleanup_operation": "delete_charge_ttl",
            },
        )
    
    logger.info(
        f"Payment confirmed | charge_id={charge.id} | external_id={charge.external_id} | value={charge.value}"
    )
