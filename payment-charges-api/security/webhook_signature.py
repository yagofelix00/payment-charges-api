import hmac
import hashlib
from flask import request, current_app, jsonify
from functools import wraps

def verify_webhook_signature():
    signature = request.headers.get("X-Signature")

    if not signature:
        return False

    secret = current_app.config["WEBHOOK_SECRET"].encode()
    payload = request.get_data()  # RAW BODY

    expected_signature = hmac.new(
        secret,
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)

def require_webhook_signature(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not verify_webhook_signature():
            return jsonify({"error": "Invalid webhook signature"}), 401
        return f(*args, **kwargs)
    return decorated

