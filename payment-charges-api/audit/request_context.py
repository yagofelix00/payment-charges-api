import uuid
from flask import g, request

REQUEST_ID_HEADER = "X-Request-Id"

def get_request_id() -> str:
    return getattr(g, "request_id", None) or "unknown"

def init_request_id():
    rid = request.headers.get(REQUEST_ID_HEADER)
    if not rid:
        rid = str(uuid.uuid4())
    g.request_id = rid
    return rid
