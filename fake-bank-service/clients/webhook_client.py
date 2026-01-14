import json
import requests
from security.hmac import sign_payload

def send_webhook(url, payload):
    body = json.dumps(payload)

    headers = {
        "Content-Type": "application/json",
        "X-Signature": sign_payload(body),
        "X-Event-Id": payload["event_id"],
        "X-Timestamp": str(payload["timestamp"])
    }

    try:
        response = requests.post(
            url,
            data=body,
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
    except Exception as e:
        print(f"[BANK] Webhook failed: {e}")
