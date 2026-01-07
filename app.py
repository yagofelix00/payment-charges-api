from flask import Flask, jsonify
from dotenv import load_dotenv
import os

from repository.database import db
from extensions import limiter
from routes.charges import charges_bp
from routes.payments import payments_bp
from exceptions.charge_exceptions import (
    ChargeNotPayable,
    InvalidChargeValue
)

load_dotenv()

app = Flask(__name__)


# Configuração do banco de dados e chave secreta para sessões e WebSockets
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['EXTERNAL_API_KEY'] = os.getenv("EXTERNAL_API_KEY")

# INIT EXTENSIONS
db.init_app(app)
limiter.init_app(app)

# REGISTER BLUEPRINTS
app.register_blueprint(charges_bp)
app.register_blueprint(payments_bp)

# ERROR HANDLERS
@app.errorhandler(ChargeNotPayable)
def handle_not_payable(e):
    return jsonify({"error": str(e)}), 400

@app.errorhandler(InvalidChargeValue)
def handle_invalid_value(e):
    return jsonify({"error": str(e)}), 400



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
