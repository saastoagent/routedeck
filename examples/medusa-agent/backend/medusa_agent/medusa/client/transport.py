from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from routedeck_core.contracts.operations import DeliveryPhase

from ...config import Settings
from .models import MedusaClientFailure, MedusaClientFailureKind


@dataclass(frozen=True)
class TransportFailureEvidence:
    delivery_phase: DeliveryPhase
    failure: MedusaClientFailure


@dataclass(frozen=True)
class HttpOutcome:
    delivery_phase: DeliveryPhase
    body: dict[str, Any] | None = None
    failure: MedusaClientFailure | None = None


class StoreApiTransport:
    """Own HTTP lifecycle, authentication headers, and delivery classification."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None,
    ) -> None:
        self._base_url = str(settings.medusa_base_url).rstrip("/")
        self._timeout = settings.medusa_timeout_seconds
        self._transport = transport
        self._headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-publishable-api-key": (
                settings.medusa_publishable_key.get_secret_value()
            ),
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> HttpOutcome:
        request_started = False
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                request_started = True
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=dict(json_body) if json_body is not None else None,
                )
        except httpx.TransportError as error:
            evidence = classify_transport_failure(
                error,
                request_started=request_started,
            )
            return HttpOutcome(
                delivery_phase=evidence.delivery_phase,
                failure=evidence.failure,
            )

        parsed_body: dict[str, Any] | None = None
        try:
            candidate = response.json()
            if isinstance(candidate, dict):
                parsed_body = candidate
        except ValueError:
            parsed_body = None

        if not 200 <= response.status_code < 300:
            return HttpOutcome(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=status_failure(response.status_code, parsed_body),
            )
        if parsed_body is None:
            return HttpOutcome(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=protocol_failure("response_json_invalid"),
            )
        return HttpOutcome(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            body=parsed_body,
        )


def classify_transport_failure(
    error: httpx.TransportError,
    *,
    request_started: bool,
) -> TransportFailureEvidence:
    """Classify by transport type and send boundary, never exception text."""

    not_sent_types = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
    phase = (
        DeliveryPhase.NOT_SENT
        if isinstance(error, not_sent_types) or not request_started
        else DeliveryPhase.POSSIBLY_SENT
    )
    code = (
        "medusa_connection_failed"
        if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout))
        else "medusa_transport_failed"
    )
    return TransportFailureEvidence(
        delivery_phase=phase,
        failure=MedusaClientFailure(
            kind=MedusaClientFailureKind.TRANSPORT,
            code=code,
            public_message="The commerce service could not be reached.",
        ),
    )


def protocol_failure(code: str) -> MedusaClientFailure:
    return MedusaClientFailure(
        kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
        code=code,
        public_message="The commerce service returned an invalid response.",
    )


def status_failure(
    status_code: int,
    body: Mapping[str, Any] | None,
) -> MedusaClientFailure:
    structured_code = None
    if body is not None:
        candidate = body.get("type") or body.get("code")
        if isinstance(candidate, str) and candidate:
            structured_code = candidate
    if status_code >= 500:
        return MedusaClientFailure(
            kind=MedusaClientFailureKind.TRANSPORT,
            code=structured_code or "medusa_unavailable",
            public_message="The commerce service is unavailable.",
        )
    return MedusaClientFailure(
        kind=MedusaClientFailureKind.BUSINESS,
        code=structured_code or f"medusa_http_{status_code}",
        public_message="The commerce service rejected the request.",
    )


__all__ = [
    "HttpOutcome",
    "StoreApiTransport",
    "TransportFailureEvidence",
    "classify_transport_failure",
    "protocol_failure",
]
