from datetime import datetime
from repository.database import db
from db_models.charges import ChargeStatus
from exceptions.charge_exceptions import (
    ChargeNotPayable,
    InvalidChargeValue
)


def check_and_expire(charge):
    if charge.status == ChargeStatus.PENDING:
        if datetime.utcnow() > charge.expires_at:
            charge.status = ChargeStatus.EXPIRED
            db.session.commit()


def confirm_payment(charge, value):
    check_and_expire(charge)

    if charge.status != ChargeStatus.PENDING:
        raise ChargeNotPayable("Charge not payable")

    if charge.value != value:
        raise InvalidChargeValue("Invalid value")

    charge.status = ChargeStatus.PAID
    charge.paid_at = datetime.utcnow()
    db.session.commit()
