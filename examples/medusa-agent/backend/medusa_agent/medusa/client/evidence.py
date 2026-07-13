from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import CompleteCartResult, OrderResult


@dataclass(frozen=True)
class StoreCallEvidence:
    """Sanitized adapter-owned coordinates for one measured Store call."""

    operation: str
    method: str
    path_template: str
    transport_kind: str


class MedusaStoreEvidenceSink(Protocol):
    async def record_complete_cart(
        self,
        call: StoreCallEvidence,
        result: CompleteCartResult,
    ) -> None: ...

    async def record_get_order(
        self,
        call: StoreCallEvidence,
        order_id: str,
        result: OrderResult,
    ) -> None: ...


__all__ = ["MedusaStoreEvidenceSink", "StoreCallEvidence"]
