from flask import Flask, jsonify, g
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
from audit.request_context import init_request_id, REQUEST_ID_HEADER

# Load environment variables from .env for local development
load_dotenv()

app = Flask(__name__)

# Register webhook routes early to ensure proper request handling
app.register_blueprint(webhooks_bp)

# Database configuration

# Use an absolute path for SQLite to avoid issues with different
# working directories (CLI, Docker, gunicorn, etc.).
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "database.db")

# Ensure instance directory exists before SQLite initialization
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"

# Security-related configuration
app.config["EXTERNAL_API_KEY"] = os.getenv("EXTERNAL_API_KEY")
app.config["WEBHOOK_SECRET"] = os.getenv("WEBHOOK_SECRET")

# Fail fast if critical security config is missing
if not app.config["WEBHOOK_SECRET"]:
    raise RuntimeError("WEBHOOK_SECRET not configured")

# MIDDLEWARES (OBSERVABILITY)
# Initialize request correlation ID at the beginning of each request
@app.before_request
def _before_request():
    init_request_id()

# Propagate request_id back to the caller for cross-service tracing
@app.after_request
def _after_request(response):
    response.headers[REQUEST_ID_HEADER] = g.request_id
    return response

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


# ENTRYPOINT
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)

