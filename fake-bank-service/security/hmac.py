import hmac
import hashlib
from config import Config

def sign_payload(payload: str) -> str:
    signature = hmac.new(
        Config.WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"sha256={signature}"

