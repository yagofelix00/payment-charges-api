import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "super-secret-key")
