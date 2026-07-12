from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from jsonschema.validators import validator_for
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from ..contracts.failures import FailureKind, RouteDeckFailure
from ..contracts.operations import (
    OperationDisposition,
    OperationRequest,
    OperationSpec,
)
from ..contracts.projection import FrozenJsonObject
from ..contracts.session import RouteDeckSession
from ..ports.executor import ResolvedEntityInput
from ..state.session import require_compatible_session
from .outcomes import canonical_json_fingerprint


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProviderInvocationContext(_FrozenContract):
    session: RouteDeckSession
    request: OperationRequest
    attempt_id: str = Field(min_length=1)


class ProviderResult(_FrozenContract):
    values: FrozenJsonObject = Field(default_factory=lambda: FrozenJsonObject({}))


class GuardInvocationContext(_FrozenContract):
    session: RouteDeckSession
    request: OperationRequest
    attempt_id: str = Field(min_length=1)
    provider_values: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )
    resolved_entities: tuple[ResolvedEntityInput, ...] = ()


class GuardDecision(_FrozenContract):
    allowed: bool
    disposition: OperationDisposition | None = None
    failure: RouteDeckFailure | None = None

    @model_validator(mode="after")
    def _valid_decision(self) -> GuardDecision:
        if self.allowed:
            if self.disposition is not None or self.failure is not None:
                raise ValueError("allowed guard decisions cannot contain denial data")
            return self
        if self.failure is None:
            raise ValueError("denied guard decisions require a typed failure")
        if self.disposition not in {
            OperationDisposition.BLOCKED,
            OperationDisposition.NEEDS_INPUT,
        }:
            raise ValueError("denied guards require blocked or needs_input disposition")
        return self

    @classmethod
    def allowed_result(cls) -> GuardDecision:
        return cls(allowed=True)

    @classmethod
    def blocked(cls, failure: RouteDeckFailure) -> GuardDecision:
        return cls(
            allowed=False,
            disposition=OperationDisposition.BLOCKED,
            failure=failure,
        )

    @classmethod
    def needs_input(cls, failure: RouteDeckFailure) -> GuardDecision:
        return cls(
            allowed=False,
            disposition=OperationDisposition.NEEDS_INPUT,
            failure=failure,
        )


class SupervisionPolicyMixin:
    app: Any
    _failure: Any
    _valid_json_object: Any

    def _validate_request(
        self,
        *,
        session: RouteDeckSession,
        request: OperationRequest,
        operation: OperationSpec,
    ) -> RouteDeckFailure | None:
        try:
            require_compatible_session(self.app.app, session)
        except Exception:
            return self._failure(
                request,
                kind=FailureKind.STATE_CONFLICT,
                code="session_upgrade_required",
                phase="version_validation",
                message="This session must be upgraded before it can continue.",
            )
        if session.session_version != request.expected_session_version:
            return self._failure(
                request,
                kind=FailureKind.STATE_CONFLICT,
                code="version_conflict",
                phase="version_validation",
                message="The session changed before this operation was applied.",
            )
        node = self._current_node(session)
        if (
            operation.id not in {candidate.id for candidate in node.operations}
            or operation.id in session.public_state.disabled_operation_ids
        ):
            return self._failure(
                request,
                kind=FailureKind.CONTRACT,
                code="operation_not_available",
                phase="operation_validation",
                message="That operation is not available in the current state.",
            )
        declared_provider_ids = {
            provider.id
            for provider in (*node.context_providers, *node.entity_providers)
        }
        if any(
            provider_ref.id not in declared_provider_ids
            for provider_ref in operation.provider_refs
        ):
            return self._failure(
                request,
                kind=FailureKind.CONTRACT,
                code="provider_not_declared_at_node",
                phase="operation_validation",
                message="Required operation context is unavailable here.",
            )
        declared_guard_ids = {guard.id for guard in node.guards}
        if any(
            guard_ref.id not in declared_guard_ids for guard_ref in operation.guard_refs
        ):
            return self._failure(
                request,
                kind=FailureKind.CONTRACT,
                code="guard_not_declared_at_node",
                phase="operation_validation",
                message="A required operation guard is unavailable here.",
            )
        schema = operation.input_schema_value()
        try:
            validator_type = validator_for(schema)
            validator_type.check_schema(schema)
            valid = validator_type(schema).is_valid(request.arguments.to_dict())
        except Exception:
            valid = False
        if not valid:
            return self._failure(
                request,
                kind=FailureKind.CONTRACT,
                code="invalid_operation_input",
                phase="input_validation",
                message="The operation input is invalid.",
            )
        return None

    def _resolve_entities(
        self,
        *,
        session: RouteDeckSession,
        request: OperationRequest,
        operation: OperationSpec,
    ) -> tuple[ResolvedEntityInput, ...] | None:
        node = self._current_node(session)
        declared_kinds = {provider.entity_kind for provider in node.entity_providers}
        arguments = request.arguments.to_dict()
        resolved: list[ResolvedEntityInput] = []
        for declaration in operation.entity_inputs:
            handle = arguments.get(declaration.argument_name)
            if (
                not isinstance(handle, str)
                or declaration.entity_kind not in declared_kinds
            ):
                return None
            public_matches = tuple(
                entity
                for entity in session.public_state.entity_handles
                if entity.handle == handle
                and entity.entity_kind == declaration.entity_kind
            )
            private_matches = tuple(
                binding
                for binding in session.private_state.entity_bindings
                if binding.public_handle == handle
                and binding.entity_kind == declaration.entity_kind
                and operation.id in binding.allowed_operation_ids
            )
            if len(public_matches) != 1 or len(private_matches) != 1:
                return None
            resolved.append(
                ResolvedEntityInput(
                    argument_name=declaration.argument_name,
                    entity_kind=declaration.entity_kind,
                    private_id=SecretStr(private_matches[0].private_id),
                )
            )
        return tuple(resolved)

    async def _refresh_context(
        self,
        *,
        session: RouteDeckSession,
        request: OperationRequest,
        operation: OperationSpec,
        attempt_id: str,
    ) -> tuple[FrozenJsonObject, RouteDeckFailure | None]:
        values: dict[str, object] = {}
        node = self._current_node(session)
        declared_provider_ids = {
            provider.id
            for provider in (*node.context_providers, *node.entity_providers)
        }
        for provider_ref in operation.provider_refs:
            if provider_ref.id not in declared_provider_ids:
                return FrozenJsonObject({}), self._failure(
                    request,
                    kind=FailureKind.CONTRACT,
                    code="provider_not_declared_at_node",
                    phase="context_refresh",
                    message="Required operation context is unavailable here.",
                )
            provider = self.app.bindings.providers.get(provider_ref)
            if provider is None:
                return FrozenJsonObject({}), self._failure(
                    request,
                    kind=FailureKind.CONTRACT,
                    code="missing_provider_binding",
                    phase="context_refresh",
                    message="Required operation context is unavailable.",
                )
            try:
                invocation = cast(
                    Callable[[ProviderInvocationContext], Awaitable[Any]], provider
                )
                result = await invocation(
                    ProviderInvocationContext(
                        session=session,
                        request=request,
                        attempt_id=attempt_id,
                    )
                )
            except Exception:
                return FrozenJsonObject({}), self._failure(
                    request,
                    kind=FailureKind.CONTEXT_PROVIDER,
                    code="context_provider_failed",
                    phase="context_refresh",
                    message="Required operation context could not be refreshed.",
                )
            if not isinstance(result, ProviderResult):
                return FrozenJsonObject({}), self._failure(
                    request,
                    kind=FailureKind.CONTEXT_PROVIDER,
                    code="invalid_context_provider_result",
                    phase="context_refresh",
                    message="Required operation context is invalid.",
                )
            declaration = self.app.app.providers.get(provider_ref.id)
            if declaration is None or not self._valid_json_object(
                declaration.output_schema_value(),
                result.values.to_dict(),
            ):
                return FrozenJsonObject({}), self._failure(
                    request,
                    kind=FailureKind.CONTEXT_PROVIDER,
                    code="invalid_context_provider_result",
                    phase="context_refresh",
                    message="Required operation context is invalid.",
                )
            values[provider_ref.id] = result.values.to_dict()
        return FrozenJsonObject(values), None

    async def _evaluate_guards(
        self,
        *,
        session: RouteDeckSession,
        request: OperationRequest,
        operation: OperationSpec,
        attempt_id: str,
        provider_values: FrozenJsonObject,
        resolved_entities: tuple[ResolvedEntityInput, ...],
    ) -> tuple[GuardDecision | None, RouteDeckFailure | None]:
        node = self._current_node(session)
        declared_guard_ids = {guard.id for guard in node.guards}
        for guard_ref in operation.guard_refs:
            if guard_ref.id not in declared_guard_ids:
                return None, self._failure(
                    request,
                    kind=FailureKind.CONTRACT,
                    code="guard_not_declared_at_node",
                    phase="guard",
                    message="A required operation guard is unavailable here.",
                )
            guard = self.app.bindings.guards.get(guard_ref)
            if guard is None:
                return None, self._failure(
                    request,
                    kind=FailureKind.CONTRACT,
                    code="missing_guard_binding",
                    phase="guard",
                    message="A required operation guard is unavailable.",
                )
            try:
                invocation = cast(
                    Callable[[GuardInvocationContext], Awaitable[Any]], guard
                )
                decision = await invocation(
                    GuardInvocationContext(
                        session=session,
                        request=request,
                        attempt_id=attempt_id,
                        provider_values=provider_values,
                        resolved_entities=resolved_entities,
                    )
                )
            except Exception:
                return None, self._failure(
                    request,
                    kind=FailureKind.GUARD,
                    code="guard_failed",
                    phase="guard",
                    message="The operation could not be safely evaluated.",
                )
            if not isinstance(decision, GuardDecision):
                return None, self._failure(
                    request,
                    kind=FailureKind.GUARD,
                    code="invalid_guard_result",
                    phase="guard",
                    message="The operation guard returned an invalid decision.",
                )
            if not decision.allowed:
                return decision, None
        return GuardDecision.allowed_result(), None

    def _context_fingerprint(
        self,
        *,
        provider_values: FrozenJsonObject,
        resolved_entities: tuple[ResolvedEntityInput, ...],
    ) -> str:
        return canonical_json_fingerprint(
            "routedeck.authoritative-context.v1",
            {
                "providers": provider_values.to_dict(),
                "entities": [
                    {
                        "argument_name": entity.argument_name,
                        "entity_kind": entity.entity_kind,
                        "private_id": entity.private_id.get_secret_value(),
                    }
                    for entity in resolved_entities
                ],
            },
        )

    def _current_node(self, session: RouteDeckSession) -> Any:
        return next(
            node
            for node in self.app.app.spec.nodes
            if node.id == session.current.node_id
        )


__all__ = [
    "GuardDecision",
    "GuardInvocationContext",
    "ProviderInvocationContext",
    "ProviderResult",
    "SupervisionPolicyMixin",
]
