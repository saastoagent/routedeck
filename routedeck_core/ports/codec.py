from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SensitiveCodec(Protocol):
    """Encrypt and decrypt private bytes without a plaintext mode."""

    def encrypt(self, value: bytes) -> bytes: ...

    def decrypt(self, value: bytes) -> bytes: ...


__all__ = ["SensitiveCodec"]
