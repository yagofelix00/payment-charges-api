import os


class Config:
    # Target URL for webhook delivery.
    # This should point to the payment receiver API and is environment-driven
    # to support different environments (local, staging, production).
    WEBHOOK_URL = os.getenv(
        "WEBHOOK_URL",
        "http://localhost:6000/webhooks/pix"
    )

    # Shared HMAC secret used to sign webhook payloads.
    # Must match the secret configured in the receiving service
    # to guarantee authenticity and integrity of webhook events.
    WEBHOOK_SECRET = os.getenv(
        "WEBHOOK_SECRET",
        "super-secret"
    )

    # Retry and backoff configuration for webhook delivery.
    # Tuned via environment variables to avoid code changes
    # when adjusting reliability or traffic behavior.
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
    INITIAL_DELAY_SECONDS = float(os.getenv("INITIAL_DELAY_SECONDS", "1"))
    BACKOFF_MULTIPLIER = float(os.getenv("BACKOFF_MULTIPLIER", "2"))
    MAX_DELAY_SECONDS = float(os.getenv("MAX_DELAY_SECONDS", "10"))

    # Network timeout for outbound webhook requests.
    # Prevents the fake bank from blocking on slow or unresponsive receivers.
    TIMEOUT_SECONDS = float(os.getenv("TIMEOUT_SECONDS", "5"))



