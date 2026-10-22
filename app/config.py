import os
import re

from dotenv import load_dotenv

load_dotenv()


def _duration_to_seconds(value: str) -> int:
    """'3600' | '30m' | '1h' | '7d' -> seconds"""
    m = re.fullmatch(r"(\d+)\s*([smhd]?)", value.strip().lower())
    if not m:
        return 3600
    amount, unit = int(m.group(1)), m.group(2) or "s"
    return amount * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


PORT = int(os.getenv("PORT", "3000"))
BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me-please-use-a-long-random-string")
JWT_EXPIRES_SECONDS = _duration_to_seconds(os.getenv("JWT_EXPIRES_IN", "1h"))

# ---- OTP ----
OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60
OTP_RESEND_COOLDOWN_SECONDS = 30
OTP_MAX_ATTEMPTS = 5
OTP_DEV_MODE = os.getenv("OTP_DEV_MODE", "true").lower() != "false"

# "console" (terminal OTP, no account) or "messagecentral" (real SMS via Message Central VerifyNow)
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "console").lower()

# ---- Message Central ----
MC_BASE_URL = os.getenv("MESSAGECENTRAL_BASE_URL", "https://cpaas.messagecentral.com")
MC_CUSTOMER_ID = os.getenv("MESSAGECENTRAL_CUSTOMER_ID")
MC_PASSWORD = os.getenv("MESSAGECENTRAL_PASSWORD")  # plain password; the code Base64-encodes it
MC_EMAIL = os.getenv("MESSAGECENTRAL_EMAIL")  # optional
MC_COUNTRY = os.getenv("MESSAGECENTRAL_COUNTRY", "91")

# ---- OAuth ----
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
