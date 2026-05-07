"""
Field-level encryption for sensitive user data (email, phone).

- Encrypted fields: stored as Fernet ciphertext in the DB (unreadable without the key)
- Hash fields:      SHA-256 HMAC used for DB lookups (unique constraints, auth)

The FIELD_ENCRYPTION_KEY must be a valid Fernet key (32 url-safe base64 bytes).
Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
    if not key:
        raise RuntimeError(
            'FIELD_ENCRYPTION_KEY is not set. '
            'Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    """Encrypt a string value. Returns empty string for empty input."""
    if not value:
        return ''
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a Fernet-encrypted string. Returns empty string for empty input."""
    if not value:
        return ''
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return value  # already plain (e.g. legacy unencrypted value)


def make_hash(value: str) -> str:
    """SHA-256 HMAC of a normalised value — used for indexed lookups."""
    if not value:
        return ''
    secret = getattr(settings, 'FIELD_ENCRYPTION_KEY', 'fallback').encode()
    return hmac.new(secret, value.strip().lower().encode(), hashlib.sha256).hexdigest()
