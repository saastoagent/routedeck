from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from routedeck_core.contracts.operations import DeliveryPhase

from .errors import MedusaClientContractError
from .models import Cart, CartResult, MedusaClientFailure
from .transport import HttpOutcome, protocol_failure


def cart_result(outcome: HttpOutcome, *, key: str) -> CartResult:
    if outcome.failure is not None:
        return CartResult.failed(
            delivery_phase=outcome.delivery_phase,
            failure=outcome.failure,
        )
    parsed = parse_resource(outcome.body, key, Cart, "cart_schema_invalid")
    if isinstance(parsed, MedusaClientFailure):
        return CartResult.failed(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            failure=parsed,
        )
    return CartResult.succeeded(parsed)


def parse_resource(
    body: dict[str, Any] | None,
    key: str,
    model: type[Any],
    failure_code: str,
) -> Any | MedusaClientFailure:
    try:
        value = required_body(body).get(key)
        if not isinstance(value, Mapping):
            raise TypeError(key)
        return model.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        return protocol_failure(failure_code)


def required_body(body: dict[str, Any] | None) -> dict[str, Any]:
    if body is None:
        raise TypeError("response body")
    return body


def required_list(body: dict[str, Any] | None, key: str) -> list[Any]:
    value = required_body(body).get(key)
    if not isinstance(value, list):
        raise TypeError(key)
    if any(not isinstance(item, Mapping) for item in value):
        raise TypeError(key)
    return value


def required_int(body: Mapping[str, Any], key: str) -> int:
    value = body.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(key)
    return value


def require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise MedusaClientContractError(f"{name} must be a non-empty string")


def promote_after_write(
    phase: DeliveryPhase,
    *,
    prior_write: bool,
) -> DeliveryPhase:
    if prior_write and phase is DeliveryPhase.NOT_SENT:
        return DeliveryPhase.POSSIBLY_SENT
    return phase


__all__ = [
    "cart_result",
    "parse_resource",
    "promote_after_write",
    "require_identifier",
    "required_body",
    "required_int",
    "required_list",
]
