import json
import time
import random
import requests

from security.hmac import sign_payload

# Retry / backoff config
DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_MAX_RETRIES = 5
DEFAULT_INITIAL_DELAY_SECONDS = 1.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_MAX_DELAY_SECONDS = 30.0
DEFAULT_JITTER_RATIO = 0.20  # 20% jitter


def _sleep_with_jitter(base_delay: float) -> float:
    """
    Adds jitter (+/- %) to avoid retry spikes (thundering herd).
    """
    jitter = base_delay * DEFAULT_JITTER_RATIO
    delay = base_delay + random.uniform(-jitter, jitter)
    return max(0.0, delay)


def send_webhook(
    url: str,
    payload: dict,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay_seconds: float = DEFAULT_INITIAL_DELAY_SECONDS,
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
) -> bool:
    """
    Sends a webhook with:
    - HMAC signature (sha256)
    - Timestamp header
    - Event ID header
    - Retry with exponential backoff + jitter

    Returns True if delivered (2xx), False otherwise.
    """

    if not url:
        raise ValueError("Webhook URL is required")

    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dict")

    event_id = payload.get("event_id")
    if not event_id:
        raise ValueError("payload['event_id'] is required")

    # Stable JSON (important for HMAC)
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    timestamp = str(int(time.time()))

    # HMAC signature over RAW body
    signature = sign_payload(body)  # expects "sha256=<hex>"

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Timestamp": timestamp,
        "X-Event-Id": event_id,
    }

    delay = float(initial_delay_seconds)

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url=url,
                data=body,          # RAW body
                headers=headers,
                timeout=timeout_seconds,
            )

            if 200 <= response.status_code < 300:
                print(
                    f"[BANK] Webhook delivered | "
                    f"event_id={event_id} | attempt={attempt}"
                )
                return True

            print(
                f"[BANK] Webhook failed | "
                f"status={response.status_code} | "
                f"event_id={event_id} | attempt={attempt}"
            )

        except requests.RequestException as exc:
            print(
                f"[BANK] Webhook error | "
                f"event_id={event_id} | attempt={attempt} | error={exc}"
            )

        if attempt == max_retries:
            break

        sleep_for = _sleep_with_jitter(delay)
        time.sleep(sleep_for)

        delay = min(delay * backoff_multiplier, max_delay_seconds)

    print(
        f"[BANK] Webhook permanently failed after retries | event_id={event_id}"
    )
    return False

