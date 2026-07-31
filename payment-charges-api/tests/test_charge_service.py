from decimal import Decimal

import pytest
from flask import Flask

from db_models.charges import Charge, ChargeStatus
from exceptions.charge_exceptions import ChargeNotPayable
from repository.database import db
from services import charge_service
from services.charge_service import confirm_payment


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


class FailingDeleteRedis:
    def __init__(self, failing_key):
        self.failing_key = failing_key
        self.delete_calls = []

    def delete(self, key):
        self.delete_calls.append(key)

        if key == self.failing_key:
            raise RuntimeError("redis cleanup failed")

        return 1


def test_confirm_payment_checks_status_before_parsing_value(app):
    with app.app_context():
        charge = Charge(
            value=Decimal("100.00"),
            status=ChargeStatus.PAID.value,
            external_id="ext-paid-invalid-confirm-value",
        )
        db.session.add(charge)
        db.session.commit()

        with pytest.raises(ChargeNotPayable):
            confirm_payment(charge, "abc")

        refreshed = db.session.get(Charge, charge.id)
        assert refreshed.status == ChargeStatus.PAID.value


def test_confirm_payment_deletes_ttl_by_external_id(app, fake_redis, monkeypatch):
    monkeypatch.setattr(charge_service, "redis_client", fake_redis)

    with app.app_context():
        charge = Charge(
            value=Decimal("100.00"),
            status=ChargeStatus.PENDING.value,
            external_id="external-id-different-from-db-id",
        )
        db.session.add(charge)
        db.session.commit()

        charge_id = charge.id
        external_id = charge.external_id
        ttl_key = f"charge:ttl:{external_id}"
        cache_key = f"charge:{charge_id}"

        fake_redis.setex(ttl_key, 1800, "PENDING")
        fake_redis.setex(cache_key, 300, "cached")

        assert fake_redis.exists(ttl_key) == 1
        assert fake_redis.exists(cache_key) == 1

        charge_service.confirm_payment(charge, "100.00")

        refreshed = db.session.get(Charge, charge_id)
        assert refreshed.status == ChargeStatus.PAID.value
        assert refreshed.paid_at is not None
        assert fake_redis.exists(ttl_key) == 0
        assert fake_redis.exists(cache_key) == 0


@pytest.mark.parametrize(
    "failing_key_kind",
    ["cache", "ttl"],
)
def test_confirm_payment_tolerates_redis_cleanup_failure(
    app,
    monkeypatch,
    failing_key_kind,
):
    with app.app_context():
        charge = Charge(
            value=Decimal("100.00"),
            status=ChargeStatus.PENDING.value,
            external_id=f"external-id-cleanup-failure-{failing_key_kind}",
        )
        db.session.add(charge)
        db.session.commit()

        charge_id = charge.id
        external_id = charge.external_id
        cache_key = f"charge:{charge_id}"
        ttl_key = f"charge:ttl:{external_id}"
        failing_key = cache_key if failing_key_kind == "cache" else ttl_key
        redis_stub = FailingDeleteRedis(failing_key)

        monkeypatch.setattr(charge_service, "redis_client", redis_stub)

        result = charge_service.confirm_payment(
            charge,
            "100.00",
        )

        assert result is None

        refreshed = db.session.get(Charge, charge_id)
        assert refreshed.status == ChargeStatus.PAID.value
        assert refreshed.paid_at is not None
        assert redis_stub.delete_calls == [
            cache_key,
            ttl_key,
        ]
