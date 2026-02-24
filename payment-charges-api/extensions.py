from flask_limiter import Limiter
from flask import request
from flask_limiter.util import get_remote_address
import os

def rate_limit_key():
    # Prefer API key (melhor p/ endpoints "externos"), fallback pra IP
    return request.headers.get("x-api-key") or get_remote_address()

# Local: redis://localhost:6379
# Docker: redis://redis:6379
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=REDIS_URL,
    default_limits=[]
)