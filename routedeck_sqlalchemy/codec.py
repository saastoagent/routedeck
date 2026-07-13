from __future__ import annotations

from typing import Protocol, runtime_checkable

from cryptography.fernet import Fernet, InvalidToken


class MissingEncryptionKey(RuntimeError):
    pass


class InvalidEncryptionKey(ValueError):
    pass


class SensitiveDataIntegrityError(RuntimeError):
    pass


@runtime_checkable
class SensitiveCodec(Protocol):
    def encrypt(self, value: bytes) -> bytes: ...

    def decrypt(self, value: bytes) -> bytes: ...


class FernetSensitiveCodec:
    """Authenticated encryption for private RouteDeck persistence."""

    def __init__(self, key: str | bytes) -> None:
        if not key:
            raise MissingEncryptionKey("ROUTEDECK_STATE_ENCRYPTION_KEY is required")
        try:
            encoded = key.encode("ascii") if isinstance(key, str) else bytes(key)
            self._fernet = Fernet(encoded)
        except (UnicodeEncodeError, TypeError, ValueError) as error:
            raise InvalidEncryptionKey(
                "ROUTEDECK_STATE_ENCRYPTION_KEY must be a valid Fernet key"
            ) from error

    def encrypt(self, value: bytes) -> bytes:
        if not isinstance(value, bytes):
            raise TypeError("sensitive values must be bytes")
        return self._fernet.encrypt(value)

    def decrypt(self, value: bytes) -> bytes:
        if not isinstance(value, bytes):
            raise TypeError("encrypted values must be bytes")
        try:
            return self._fernet.decrypt(value)
        except InvalidToken as error:
            raise SensitiveDataIntegrityError(
                "encrypted RouteDeck data failed authentication"
            ) from error


__all__ = [
    "FernetSensitiveCodec",
    "InvalidEncryptionKey",
    "MissingEncryptionKey",
    "SensitiveCodec",
    "SensitiveDataIntegrityError",
]
