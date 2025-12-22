from flask import Flask, request, jsonify
from repository.database import db
from db_models.charges import Charge, ChargeStatus  
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)

# Configuração do banco de dados e chave secreta para sessões e WebSockets
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'SECRET_KEY_WEBSOCKET'

db.init_app(app)

# REGRA DE NEGÓCIO: Verifica e expira cobranças pendentes
def check_and_expire(charge):
    if charge.status == ChargeStatus.PENDING:
        if datetime.utcnow() > charge.expires_at:
            charge.status = ChargeStatus.EXPIRED
            db.session.commit()


@app.route("/charges", methods=["POST"])
def create_charge():
    data = request.get_json()

    if not data or "value" not in data:
        return jsonify({"error": "Value is required"}), 400

    if data["value"] <= 0:
        return jsonify({"error": "Invalid value"}), 400

    charge = Charge(
        value=data["value"],
        status=ChargeStatus.PENDING,
        external_id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )


    db.session.add(charge)
    db.session.commit()

    return jsonify({"id": charge.id,
                    "external_id": charge.external_id,
                    "status": charge.status.value}), 201


@app.route("/charges/<int:charge_id>", methods=["GET"])
def get_charge(charge_id):
    charge = Charge.query.get(charge_id)

    if not charge:
        return jsonify({"error": "Charge not found"}), 404

    check_and_expire(charge)

    return jsonify({
        "id": charge.id,
        "value": charge.value,
        "status": charge.status.value,
        "expires_at": charge.expires_at.isoformat()
    })


@app.route("/external/payments", methods=["POST"])
def external_payment():
    data = request.get_json()
    
    if not data or "external_id" not in data or "value" not in data:
        return jsonify({"error": "Invalid payload"}), 400
    
    charge = Charge.query.filter_by(
        external_id=data.get("external_id")
    ).first()

    if not charge:
        return jsonify({"error": "Invalid external_id"}), 400

    check_and_expire(charge)

    if charge.status != ChargeStatus.PENDING:
        return jsonify({"error": "Charge not payable"}), 400

    if data.get("value") != charge.value:
        return jsonify({"error": "Invalid value"}), 400

    charge.status = ChargeStatus.PAID
    charge.paid_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"message": "Payment confirmed"})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
