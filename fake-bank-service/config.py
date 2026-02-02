import os

class Config:
    # URL que o banco chama (API de pagamentos)
    WEBHOOK_URL = os.getenv(
        "WEBHOOK_URL",
        "http://localhost:6000/webhooks/pix"
    )

    # Segredo HMAC (deve bater com o receiver)
    WEBHOOK_SECRET = os.getenv(
        "WEBHOOK_SECRET",
        "super-secret"
    )

    # Retry / Backoff
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
    INITIAL_DELAY_SECONDS = float(os.getenv("INITIAL_DELAY_SECONDS", "1"))
    BACKOFF_MULTIPLIER = float(os.getenv("BACKOFF_MULTIPLIER", "2"))
    MAX_DELAY_SECONDS = float(os.getenv("MAX_DELAY_SECONDS", "10"))

    TIMEOUT_SECONDS = float(os.getenv("TIMEOUT_SECONDS", "5"))


