"""Security helpers for sensitive Lynk & Co remote commands."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os

PBKDF2_ITERATIONS = 200_000


def create_pin_hash(pin: str) -> tuple[str, str]:
    """Return (salt_hex, hash_hex) for a numeric security PIN."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return salt.hex(), digest.hex()


def verify_pin(pin: str, salt_hex: str, hash_hex: str) -> bool:
    """Verify a PIN without storing or logging the clear-text PIN."""
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(actual, expected)


class VehicleSecurityManager:
    """In-memory authorization window for high-risk vehicle commands."""

    def __init__(
        self,
        *,
        enabled: bool,
        pin_salt: str,
        pin_hash: str,
        authorization_minutes: int,
    ) -> None:
        self.enabled = enabled
        self.pin_salt = pin_salt
        self.pin_hash = pin_hash
        self.authorization_minutes = authorization_minutes
        self._authorized_until: datetime | None = None

    @property
    def configured(self) -> bool:
        return bool(self.pin_salt and self.pin_hash)

    @property
    def authorized(self) -> bool:
        if not self.enabled:
            return True
        if self._authorized_until is None:
            return False
        return datetime.now(timezone.utc) < self._authorized_until

    @property
    def authorized_until(self) -> datetime | None:
        return self._authorized_until

    def authorize(self, pin: str) -> bool:
        if not self.enabled:
            return True
        if not self.configured:
            return False
        if not verify_pin(pin, self.pin_salt, self.pin_hash):
            return False
        self._authorized_until = datetime.now(timezone.utc) + timedelta(
            minutes=self.authorization_minutes
        )
        return True

    def lock(self) -> None:
        self._authorized_until = None

    def update(
        self,
        *,
        enabled: bool,
        pin_salt: str,
        pin_hash: str,
        authorization_minutes: int,
    ) -> None:
        self.enabled = enabled
        self.pin_salt = pin_salt
        self.pin_hash = pin_hash
        self.authorization_minutes = authorization_minutes
        self.lock()
