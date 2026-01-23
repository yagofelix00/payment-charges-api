import logging
from logging.handlers import RotatingFileHandler
import os
from audit.request_context import get_request_id

LOG_DIR = "logs"
LOG_FILE = "audit.log"

os.makedirs(LOG_DIR, exist_ok=True)

_base_logger = logging.getLogger("audit_logger")
_base_logger.setLevel(logging.INFO)

# Avoid duplicated handlers if Flask reloads in debug mode
if not _base_logger.handlers:
    handler = RotatingFileHandler(
        filename=os.path.join(LOG_DIR, LOG_FILE),
        maxBytes=5_000_000,  # 5MB
        backupCount=3
    )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | request_id=%(request_id)s | %(message)s"
    )

    handler.setFormatter(formatter)
    _base_logger.addHandler(handler)


class RequestIdAdapter(logging.LoggerAdapter):
    """
    Injects request_id into log records automatically.
    Works for all logs emitted during a Flask request.
    """
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra.setdefault("request_id", get_request_id())
        kwargs["extra"] = extra
        return msg, kwargs


logger = RequestIdAdapter(_base_logger, {})

