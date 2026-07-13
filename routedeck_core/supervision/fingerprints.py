from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from ..contracts.operations import EntityInputSpec, OperationRequest, OperationSpec


_REQUEST_FINGERPRINT_DOMAIN = "routedeck.operation-request.v1"
_OPERATION_SPEC_DOMAIN = "routedeck.operation-spec.v1"


def canonical_request_fingerprint(
    request: OperationRequest,
    *,
    entity_inputs: Sequence[EntityInputSpec] = (),
    parent_turn_id: str | None = None,
) -> str:
    """Fingerprint request identity without coupling retries to a state version."""

    raw_arguments: object = request.arguments
    if hasattr(raw_arguments, "to_dict"):
        arguments = raw_arguments.to_dict()
    elif isinstance(raw_arguments, Mapping):
        arguments = dict(raw_arguments)
    else:
        raise TypeError("Operation arguments must be a JSON object")
    entity_handles = [
        {
            "argument_name": entity_input.argument_name,
            "entity_kind": entity_input.entity_kind,
            "public_handle": arguments.get(entity_input.argument_name),
        }
        for entity_input in entity_inputs
    ]
    payload = {
        "domain": _REQUEST_FINGERPRINT_DOMAIN,
        "session_id": request.session_id,
        "operation_id": request.operation_id,
        "source": request.source.value,
        "arguments": arguments,
        "entity_handles": entity_handles,
        "parent_turn_id": parent_turn_id,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"rdop1:{hashlib.sha256(canonical).hexdigest()}"


def canonical_json_fingerprint(domain: str, value: Any) -> str:
    """Hash a typed JSON value under an explicit protocol domain."""

    canonical = json.dumps(
        {"domain": domain, "value": value},
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def canonical_operation_spec_version(operation: OperationSpec) -> str:
    digest = canonical_json_fingerprint(
        _OPERATION_SPEC_DOMAIN,
        operation.model_dump(mode="json"),
    )
    return f"rdopspec1:{digest}"


__all__ = [
    "canonical_json_fingerprint",
    "canonical_operation_spec_version",
    "canonical_request_fingerprint",
]
