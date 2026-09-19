"""
Security utilities: Fernet encryption for merchant secrets,
HMAC-SHA256 verification for Razorpay webhooks.
"""

import hashlib
import hmac
import base64

from cryptography.fernet import Fernet
from app.core.settings import get_settings

settings = get_settings()

# ── Fernet key derived from SECRET_KEY ────────────────────────────────────────
# We derive a 32-byte key by SHA-256 hashing the app secret key, then
# base64url-encode it to produce a valid Fernet key.
_raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
_fernet_key = base64.urlsafe_b64encode(_raw)
_fernet = Fernet(_fernet_key)


def encrypt_secret(value: str) -> str:
    """Encrypt a plaintext secret string for storage."""
    return _fernet.encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decrypt a previously encrypted secret string."""
    return _fernet.decrypt(token.encode()).decode()


# ── Razorpay webhook HMAC verification ────────────────────────────────────────

def verify_razorpay_signature(
    raw_body: bytes,
    signature: str,
    webhook_secret: str,
) -> bool:
    """
    Verify a Razorpay webhook signature.

    Razorpay signs the raw request body with the webhook secret using
    HMAC-SHA256 and sends the hex digest in the X-Razorpay-Signature header.
    """
    expected = hmac.new(
        key=webhook_secret.encode(),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
