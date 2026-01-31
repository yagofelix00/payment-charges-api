from flask import request, jsonify, make_response
from functools import wraps
from infrastructure.redis_client import redis_client
import json


def idempotent(ttl=300):
    """
    Idempotency decorator using Redis as the response cache.

    Contract:
    - Client MUST send 'Idempotency-Key' header for mutating operations.
    - Same key within the TTL returns the same response payload, preventing duplicate side effects
      (e.g., creating the same charge twice).
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Idempotency key should be provided by the client (unique per intended operation)
            key = request.headers.get("Idempotency-Key")

            if not key:
                return jsonify({"error": "Idempotency-Key missing"}), 400

            redis_key = f"idempotency:{key}"

            # If we have a cached response, return it immediately (idempotent replay)
            cached = redis_client.get(redis_key)
            if cached:
                return jsonify(json.loads(cached))

            # Execute the original handler (first-time request for this key)
            response = f(*args, **kwargs)

            # Normalize Flask responses:
            # - View functions may return (json, status), Response objects, etc.
            # - make_response ensures we always have a proper Response to inspect.
            flask_response = make_response(response)

            # NOTE: We cache only the JSON body. If you need strict replay semantics,
            # you may also store the status code and headers.
            data = flask_response.get_json()

            # Store the response for a limited time:
            # - Prevents duplicate side effects within TTL
            # - Keeps Redis usage bounded
            redis_client.setex(
                redis_key,
                ttl,
                json.dumps(data)
            )

            return flask_response

        return wrapper
    return decorator



