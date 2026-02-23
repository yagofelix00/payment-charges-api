from flask import Blueprint, jsonify
from repository.database import db
from infrastructure.redis_client import redis_client

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@health_bp.route("/ready", methods=["GET"])
def ready():
    try:
        db.session.execute("SELECT 1")
        redis_client.ping()
        return jsonify({"status": "ready"}), 200
    except Exception:
        return jsonify({"status": "not_ready"}), 503