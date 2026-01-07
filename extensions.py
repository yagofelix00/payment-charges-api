from flask_limiter import Limiter
from flask import request
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[]
)

def rate_limit_key():
    return request.headers.get("x-api-key") or get_remote_address()

limiter = Limiter(key_func=rate_limit_key)