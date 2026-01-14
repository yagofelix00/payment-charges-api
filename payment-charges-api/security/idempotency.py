from flask import request, jsonify, make_response
from functools import wraps
from infrastructure.redis_client import redis_client
import json
import hashlib


def idempotent(ttl=300):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = request.headers.get("Idempotency-Key")

            if not key:
                return jsonify({"error": "Idempotency-Key missing"}), 400

            redis_key = f"idempotency:{key}"

            cached = redis_client.get(redis_key)
            if cached:
                return jsonify(json.loads(cached))

            response = f(*args, **kwargs)

            # 🔥 NORMALIZA resposta Flask
            flask_response = make_response(response)
            status_code = flask_response.status_code
            data = flask_response.get_json()

            redis_client.setex(
                redis_key,
                ttl,
                json.dumps(data)
            )

            return flask_response

        return wrapper
    return decorator


