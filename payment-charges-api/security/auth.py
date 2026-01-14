from flask import request, jsonify, current_app
from functools import wraps
from dotenv import load_dotenv
import os

load_dotenv()

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "API key missing"}), 401

        # Aceita padrão: Authorization: Bearer TOKEN
        if auth_header.startswith("Bearer "):
            api_key = auth_header.replace("Bearer ", "").strip()
        else:
            api_key = auth_header.strip()

        expected_key = current_app.config.get("EXTERNAL_API_KEY")

        if api_key != expected_key:
            return jsonify({"error": "Invalid API key"}), 403

        return f(*args, **kwargs)
    return decorated