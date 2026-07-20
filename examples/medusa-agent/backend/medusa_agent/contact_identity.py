from __future__ import annotations

import hashlib
import json
from typing import Protocol


class ContactAddressSource(Protocol):
    def model_dump(self, *, mode: str) -> dict[str, object]: ...


class ContactFingerprintSource(Protocol):
    @property
    def email(self) -> str | None: ...

    @property
    def shipping_address(self) -> ContactAddressSource | None: ...

    @property
    def billing_address(self) -> ContactAddressSource | None: ...


def contact_fingerprint(source: ContactFingerprintSource) -> str:
    payload = {
        "email": source.email,
        "shipping_address": (
            source.shipping_address.model_dump(mode="json")
            if source.shipping_address is not None
            else None
        ),
        "billing_address": (
            source.billing_address.model_dump(mode="json")
            if source.billing_address is not None
            else None
        ),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["ContactFingerprintSource", "contact_fingerprint"]
