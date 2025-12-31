import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
LOG_FILE = "audit.log"

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("audit_logger")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    filename=os.path.join(LOG_DIR, LOG_FILE),
    maxBytes=5_000_000,  # 5MB
    backupCount=3
)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

handler.setFormatter(formatter)
logger.addHandler(handler)
