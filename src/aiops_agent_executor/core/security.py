"""Security utilities for encryption and authentication."""

import base64
import secrets
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from aiops_agent_executor.core.config import get_settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data using AES-256."""

    def __init__(self, key: str | None = None) -> None:
        """Initialize encryption service with a key."""
        settings = get_settings()
        raw_key = (key or settings.encryption_key).encode()

        # Derive a Fernet-compatible key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"aiops-agent-executor-salt",  # In production, use a proper salt
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(raw_key))
        self._fernet = Fernet(derived_key)

    def encrypt(self, data: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext."""
        encrypted = self._fernet.encrypt(data.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64-encoded ciphertext and return plaintext."""
        decrypted = self._fernet.decrypt(encrypted_data.encode())
        return decrypted.decode()


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mask sensitive data, showing only the last few characters."""
    if len(data) <= visible_chars:
        return "*" * len(data)
    return "*" * (len(data) - visible_chars) + data[-visible_chars:]


def generate_secret_key(length: int = 32) -> str:
    """Generate a cryptographically secure random key."""
    return secrets.token_urlsafe(length)


_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get the singleton encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
