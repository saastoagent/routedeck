from __future__ import annotations

import secrets
from typing import Any

from fastapi.responses import JSONResponse

from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationResult,
)
from routedeck_core.contracts.projection import PublicProjection
from routedeck_core.navigation.transactions import NavigationTransactionError
from routedeck_core.ports import SessionStoreError
from routedeck_core.validation import (
    RouteDeckResumeCapabilityExpired,
    RouteDeckValidationError,
)

from .contracts import RouteDeckHttpProblem
from .dependencies import RouteDeckDependencyUnavailable


PRIVATE_CACHE_CONTROL = "private, no-store"


def public_projection(projection: PublicProjection) -> dict[str, Any]:
    value = projection.model_dump(mode="json")
    value["graph_node"] = projection.current.node_id
    return value


def public_operation_result(result: OperationResult) -> dict[str, Any]:
    return result.model_dump(mode="json", exclude={"session_id"})


def operation_response(result: OperationResult) -> JSONResponse:
    return JSONResponse(
        status_code=operation_status(result),
        content=public_operation_result(result),
        headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
    )


def operation_status(result: OperationResult) -> int:
    if result.disposition is OperationDisposition.NEEDS_INPUT:
        return 422
    if result.disposition is OperationDisposition.PENDING:
        return 202
    failure = result.failure
    if failure is None:
        return 200
    if failure.code in {
        "operation_not_available",
        "review_not_found",
        "route_not_found",
        "session_not_found",
    }:
        return 404
    if failure.code == "session_expired":
        return 410
    if failure.kind is FailureKind.CONTRACT:
        return 400
    if failure.kind in {
        FailureKind.STATE_CONFLICT,
        FailureKind.GUARD,
        FailureKind.REVIEW,
        FailureKind.BUSINESS,
        FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
    }:
        return 409
    if failure.kind in {
        FailureKind.CONTEXT_PROVIDER,
        FailureKind.TRANSPORT,
        FailureKind.PROVIDER_PROTOCOL,
        FailureKind.PERSISTENCE,
    }:
        return 503
    return 500


def exception_response(
    error: Exception,
    *,
    cache_control: str | None = PRIVATE_CACHE_CONTROL,
) -> JSONResponse:
    status_code, failure = failure_for_exception(error)
    headers = {"Cache-Control": cache_control} if cache_control else None
    return JSONResponse(
        status_code=status_code,
        content={"failure": failure.model_dump(mode="json")},
        headers=headers,
    )


def failure_for_exception(error: Exception) -> tuple[int, RouteDeckFailure]:
    if isinstance(error, RouteDeckHttpProblem):
        return error.status_code, transport_failure(
            kind=error.kind,
            code=error.code,
            phase=error.phase,
            public_message=error.public_message,
        )
    if isinstance(error, RouteDeckDependencyUnavailable):
        return 503, transport_failure(
            kind=FailureKind.TRANSPORT,
            code="dependency_unavailable",
            phase="dependency_resolution",
            public_message="The RouteDeck runtime is unavailable.",
        )
    if isinstance(error, SessionStoreError):
        code = error.code.value
        if code == "session_not_found":
            status = 404
        elif code == "session_expired":
            status = 410
        elif code in {
            "session_already_exists",
            "version_conflict",
            "request_id_reused",
            "operation_in_progress",
            "lease_mismatch",
            "execution_already_claimed",
            "review_already_resolved",
            "result_mismatch",
            "session_upgrade_required",
        }:
            status = 409
        elif code == "persistence_failure":
            status = 503
        else:
            status = 500
        kind = FailureKind.STATE_CONFLICT if status == 409 else FailureKind.PERSISTENCE
        return status, transport_failure(
            kind=kind,
            code=code,
            phase="session_store",
            public_message="The RouteDeck session request could not be completed.",
        )
    if isinstance(error, NavigationTransactionError):
        conflict_codes = {
            "version_conflict",
            "history_path_mismatch",
        }
        return (
            409 if error.code in conflict_codes else 400,
            transport_failure(
                kind=(
                    FailureKind.STATE_CONFLICT
                    if error.code in conflict_codes
                    else FailureKind.CONTRACT
                ),
                code=error.code,
                phase="navigation",
                public_message=error.public_message,
            ),
        )
    if isinstance(error, RouteDeckResumeCapabilityExpired):
        return 410, transport_failure(
            kind=FailureKind.STATE_CONFLICT,
            code="resume_capability_expired",
            phase="session_validation",
            public_message="The RouteDeck session resume capability has expired.",
        )
    if (
        isinstance(error, RouteDeckValidationError)
        and str(error) == "session_upgrade_required"
    ):
        return 409, transport_failure(
            kind=FailureKind.STATE_CONFLICT,
            code="session_upgrade_required",
            phase="session_validation",
            public_message="This session requires an application upgrade.",
        )
    return 500, transport_failure(
        kind=FailureKind.INTERNAL,
        code="internal_invariant",
        phase="http_transport",
        public_message="The RouteDeck request could not be completed.",
    )


def transport_failure(
    *,
    kind: FailureKind,
    code: str,
    phase: str,
    public_message: str,
) -> RouteDeckFailure:
    return RouteDeckFailure(
        kind=kind,
        code=code,
        phase=phase,
        correlation_id=secrets.token_urlsafe(12),
        public_message=public_message,
    )


__all__ = [
    "PRIVATE_CACHE_CONTROL",
    "exception_response",
    "failure_for_exception",
    "operation_response",
    "operation_status",
    "public_operation_result",
    "public_projection",
    "transport_failure",
]
