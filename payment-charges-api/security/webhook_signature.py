import hmac
import hashlib
import time
from flask import request, current_app, jsonify
from functools import wraps

# Maximum allowed time difference (in seconds) between
# the webhook event timestamp and the server time.
# This protects against replay attacks.
TOLERANCE_SECONDS = 300  # 5 minutes


def verify_webhook_signature():
    """
    Verifies the authenticity and freshness of a webhook request.

    Security checks:
    - Validates the presence of required headers
    - Protects against replay attacks using a timestamp tolerance window
    - Validates the HMAC signature using the raw request body
    """

    signature = request.headers.get("X-Signature")
    timestamp = request.headers.get("X-Timestamp")

    # Required headers must be present
    if not signature or not timestamp:
        return False

    # ⏱ Replay attack protection
    # Reject requests outside the allowed time window
    now = int(time.time())
    if abs(now - int(timestamp)) > TOLERANCE_SECONDS:
        return False

    # Raw request body must be used for signature validation
    payload = request.get_data()
    secret = current_app.config["WEBHOOK_SECRET"].encode()

    # Generate expected HMAC signature
    expected_signature = hmac.new(
        secret,
        payload,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(
        signature,
        f"sha256={expected_signature}"
    )


def require_webhook_signature(f):
    """
    Flask decorator that enforces webhook signature validation.
    Rejects the request if the signature is invalid or missing.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if not verify_webhook_signature():
            return jsonify({"error": "Invalid webhook signature"}), 401
        return f(*args, **kwargs)

    return decorated



