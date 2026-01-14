from flask import Flask, jsonify
from dotenv import load_dotenv
import os

from repository.database import db
from extensions import limiter
from routes.charges import charges_bp
from exceptions.charge_exceptions import (
    ChargeNotPayable,
    InvalidChargeValue
)
from routes.webhooks import webhooks_bp


load_dotenv()

app = Flask(__name__)
app.register_blueprint(webhooks_bp)

# Configuração do banco de dados e chave secreta para sessões e WebSockets
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['EXTERNAL_API_KEY'] = os.getenv("EXTERNAL_API_KEY")
app.config["WEBHOOK_SECRET"] = os.getenv("WEBHOOK_SECRET")

if not app.config["WEBHOOK_SECRET"]:
    raise RuntimeError("WEBHOOK_SECRET not configured")

# INIT EXTENSIONS
db.init_app(app)
limiter.init_app(app)

# REGISTER BLUEPRINTS
app.register_blueprint(charges_bp)

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
