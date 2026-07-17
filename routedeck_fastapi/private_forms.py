from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from fastapi.responses import JSONResponse

from routedeck_core.contracts.failures import FailureKind
from routedeck_core.contracts.mutations import (
    MutationKind,
    MutationRecord,
    MutationStatus,
)
from routedeck_core.contracts.projection import ProjectedSurface, PublicProjection
from routedeck_core.contracts.session import PrivateDraft, SessionSnapshot
from routedeck_core.contracts.surfaces import PrivateFormBinding

from .contracts import PrivateFormWriteRequest, RouteDeckHttpProblem
from routedeck_core.ports import SensitiveCodec

from .dependencies import RouteDeckDependencies
from .responses import PRIVATE_CACHE_CONTROL
from .session_http import project


def private_draft(snapshot: SessionSnapshot, form_id: str) -> PrivateDraft | None:
    return next(
        (
            draft
            for draft in snapshot.state.private_state.drafts
            if draft.form_id == form_id
        ),
        None,
    )


def authorized_private_form(
    dependencies: RouteDeckDependencies,
    snapshot: SessionSnapshot,
    form_id: str,
) -> PrivateFormBinding:
    projection = project(dependencies, snapshot)
    node = next(
        (
            candidate
            for candidate in dependencies.app.graph.nodes
            if candidate.id == snapshot.state.current.node_id
        ),
        None,
    )
    if node is None:
        raise RouteDeckHttpProblem(
            500,
            "private_form_binding_invalid",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_authorization",
        )
    surface_specs = {
        surface.id: surface for surface in node.surfaces.declared_surfaces()
    }
    matches: list[PrivateFormBinding] = []
    seen_surface_ids: set[str] = set()
    for surface in projected_surfaces(projection):
        if surface.surface_id in seen_surface_ids:
            continue
        seen_surface_ids.add(surface.surface_id)
        spec = surface_specs.get(surface.surface_id)
        binding = spec.private_form_binding if spec is not None else None
        if binding is None:
            continue
        props = {value.name: value.value.to_python() for value in surface.props}
        projected_form_id = props.get(binding.form_id_prop)
        if not isinstance(projected_form_id, str) or not projected_form_id:
            raise RouteDeckHttpProblem(
                500,
                "private_form_binding_invalid",
                "The private form could not be loaded.",
                FailureKind.INTERNAL,
                "private_form_authorization",
            )
        if projected_form_id == form_id:
            matches.append(binding)
    if not matches:
        raise RouteDeckHttpProblem(
            404,
            "private_form_not_found",
            "That private form is unavailable.",
        )
    if len(matches) != 1:
        raise RouteDeckHttpProblem(
            500,
            "private_form_binding_invalid",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_authorization",
        )
    return matches[0]


def projected_surfaces(projection: PublicProjection) -> tuple[ProjectedSurface, ...]:
    slots = projection.surfaces
    projected = (
        slots.active,
        *slots.frame,
        *slots.peer,
        *slots.detail,
        *slots.form,
        *slots.review,
        *slots.status,
        *slots.error,
        *slots.diagnostic,
    )
    return tuple(surface for surface in projected if surface is not None)


async def private_form_state(
    *,
    dependencies: RouteDeckDependencies,
    snapshot: SessionSnapshot,
    form_id: str,
    binding: PrivateFormBinding,
) -> tuple[PrivateDraft | None, bytes | None, dict[str, Any] | None]:
    draft = private_draft(snapshot, form_id)
    encrypted = await dependencies.store.load_private_blob(
        snapshot.session_id,
        form_id,
    )
    if (draft is None) != (encrypted is None):
        raise RouteDeckHttpProblem(
            500,
            "private_form_state_mismatch",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_load",
        )
    if draft is None or encrypted is None:
        return draft, encrypted, None
    value = decrypt_private_form(dependencies.private_form_codec, encrypted)
    if tuple(sorted(value)) != draft.field_names:
        raise RouteDeckHttpProblem(
            500,
            "private_form_schema_mismatch",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_load",
        )
    require_allowed_private_form_fields(
        binding,
        draft.field_names,
        stored=True,
    )
    return draft, encrypted, value


def require_allowed_private_form_fields(
    binding: PrivateFormBinding,
    field_names: tuple[str, ...],
    *,
    stored: bool,
) -> None:
    unexpected = set(field_names).difference(binding.allowed_field_names)
    if not unexpected:
        return
    raise RouteDeckHttpProblem(
        500 if stored else 400,
        "private_form_schema_mismatch" if stored else "private_form_fields_undeclared",
        "The private form could not be loaded."
        if stored
        else "The private form contains undeclared fields.",
        FailureKind.INTERNAL if stored else FailureKind.CONTRACT,
        "private_form_load" if stored else "private_form_validation",
    )


def private_form_fingerprint(
    form_id: str,
    request: PrivateFormWriteRequest,
) -> str:
    canonical = json.dumps(
        {
            "complete": request.complete,
            "form_id": form_id,
            "value": request.value,
        },
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def private_form_replay_response(
    record: MutationRecord,
    *,
    fingerprint: str,
    form_id: str,
) -> JSONResponse:
    if (
        record.kind is not MutationKind.PRIVATE_FORM
        or record.request_fingerprint != fingerprint
    ):
        raise RouteDeckHttpProblem(
            409,
            "request_id_reused",
            "This request ID was already used for another mutation.",
            FailureKind.STATE_CONFLICT,
            "mutation_replay",
        )
    if record.status is not MutationStatus.COMPLETED:
        raise RouteDeckHttpProblem(
            500,
            "mutation_record_invalid",
            "The private form result could not be replayed.",
            FailureKind.INTERNAL,
            "mutation_replay",
        )
    result = record.result.to_dict()
    if (
        set(result) != {"complete", "form_id", "revision"}
        or result.get("form_id") != form_id
        or not isinstance(result.get("complete"), bool)
        or not isinstance(result.get("revision"), int)
        or isinstance(result.get("revision"), bool)
    ):
        raise RouteDeckHttpProblem(
            500,
            "mutation_record_invalid",
            "The private form result could not be replayed.",
            FailureKind.INTERNAL,
            "mutation_replay",
        )
    return JSONResponse(
        content={
            **result,
            "session_version": record.committed_session_version,
            "projection_version": record.committed_projection_version,
        },
        headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
    )


def encrypt_private_form(codec: SensitiveCodec, value: Mapping[str, Any]) -> bytes:
    try:
        plaintext = json.dumps(
            dict(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return codec.encrypt(plaintext)
    except Exception as error:
        raise RouteDeckHttpProblem(
            500,
            "private_form_encryption_failed",
            "The private form could not be saved.",
            FailureKind.INTERNAL,
            "private_form_encrypt",
        ) from error


def decrypt_private_form(codec: SensitiveCodec, encrypted: bytes) -> dict[str, Any]:
    try:
        value = json.loads(codec.decrypt(encrypted))
    except Exception as error:
        raise RouteDeckHttpProblem(
            500,
            "private_form_decryption_failed",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_decrypt",
        ) from error
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RouteDeckHttpProblem(
            500,
            "private_form_payload_invalid",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_decrypt",
        )
    return value


__all__ = [
    "authorized_private_form",
    "decrypt_private_form",
    "encrypt_private_form",
    "private_draft",
    "private_form_fingerprint",
    "private_form_replay_response",
    "private_form_state",
    "projected_surfaces",
    "require_allowed_private_form_fields",
]
