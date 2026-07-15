from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from ....config import Settings
from ..evidence import MedusaStoreEvidenceSink, StoreCallEvidence
from ..models import CompleteCartResult, OrderResult
from ..transport import HttpOutcome, StoreApiTransport


class MedusaResourceClient:
    """Shared request and measured-evidence path for typed Store resources."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        evidence_sink: MedusaStoreEvidenceSink | None = None,
    ) -> None:
        self._http = StoreApiTransport(settings, transport)
        self._evidence_sink = evidence_sink
        self._transport_kind = "network" if transport is None else "injected"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> HttpOutcome:
        return await self._http.request(
            method,
            path,
            params=params,
            json_body=json_body,
        )

    def evidence(
        self,
        *,
        operation: str,
        method: str,
        path_template: str,
    ) -> StoreCallEvidence:
        return StoreCallEvidence(
            operation=operation,
            method=method,
            path_template=path_template,
            transport_kind=self._transport_kind,
        )

    async def record_complete_cart(
        self,
        call: StoreCallEvidence,
        result: CompleteCartResult,
    ) -> CompleteCartResult:
        if self._evidence_sink is not None:
            await self._evidence_sink.record_complete_cart(call, result)
        return result

    async def record_get_order(
        self,
        call: StoreCallEvidence,
        order_id: str,
        result: OrderResult,
    ) -> OrderResult:
        if self._evidence_sink is not None:
            await self._evidence_sink.record_get_order(call, order_id, result)
        return result


__all__ = ["MedusaResourceClient"]
