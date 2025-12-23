from flask import request, jsonify, current_app

def require_api_key():
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return jsonify({"error": "Missing Authorization header"}), 401

    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Invalid authorization format"}), 401

    token = auth_header.replace("Bearer ", "")

    if token != current_app.config['EXTERNAL_API_KEY']:
        return jsonify({"error": "Invalid API key"}), 403
