from flask import request, jsonify, current_app
from functools import wraps
from dotenv import load_dotenv
import os

load_dotenv()

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("x-api-key")

        if not api_key:
            return jsonify({"error": "API key missing"}), 401

        if api_key != current_app.config["EXTERNAL_API_KEY"]:
            return jsonify({"error": "Invalid API key"}), 403

        return f(*args, **kwargs)
    return decorated