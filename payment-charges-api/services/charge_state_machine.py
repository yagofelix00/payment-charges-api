from datetime import datetime
from enum import Enum

from repository.database import db


class ChargeState(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"


ALLOWED_TRANSITIONS = {
    ChargeState.PENDING: {ChargeState.PAID, ChargeState.EXPIRED},
    ChargeState.PAID: set(),
    ChargeState.EXPIRED: set(),
}


class InvalidChargeTransition(Exception):
    pass


def _normalize_state(raw_state) -> ChargeState:
    if isinstance(raw_state, Enum):
        return ChargeState(raw_state.value)
    return ChargeState(str(raw_state))


def transition_charge(charge, new_state) -> None:
    current_state = _normalize_state(charge.status)
    target_state = _normalize_state(new_state)

    if target_state not in ALLOWED_TRANSITIONS[current_state]:
        raise InvalidChargeTransition(
            f"Invalid charge transition: {current_state.value} -> {target_state.value}"
        )

    charge.status = target_state.value
    if target_state == ChargeState.PAID and charge.paid_at is None:
        charge.paid_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
