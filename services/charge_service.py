from datetime import datetime
from repository.database import db
from db_models.charges import ChargeStatus
from exceptions.charge_exceptions import (
    ChargeNotPayable,
    InvalidChargeValue
)
from audit.logger import logger
from infrastructure.redis_client import redis_client


def confirm_payment(charge, value):

    if charge.status != ChargeStatus.PENDING:
        logger.warning(
            f"Invalid payment attempt | charge_id={charge.id} | status={charge.status}"
        )
        raise ChargeNotPayable("Charge not payable")

    if charge.value != value:
        logger.warning(
            f"Payment value mismatch | charge_id={charge.id} | expected={charge.value} | received={value}"
        )
        raise InvalidChargeValue("Invalid value")

    charge.status = ChargeStatus.PAID
    charge.paid_at = datetime.utcnow()
    db.session.commit()

    # Limpa TODOS os caches
    redis_client.delete(f"charge:{charge.id}")
    redis_client.delete(f"charge:ttl:{charge.id}")
    
    logger.info(
        f"Payment confirmed | charge_id={charge.id} | external_id={charge.external_id} | value={charge.value}"
    )