from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..app import CompiledApplication
from ..contracts.application import Node
from ..contracts.session import RouteDeckSession
from ..navigation.routes import PublicRouteKeyValidator
from ..navigation.session_location import validate_session_location
from ..validation import RouteDeckValidationError
from .providers import OperationContextScope


@dataclass(frozen=True)
class ContextScopeBuilder:
    """Build model/tool context from declared and currently bound data only."""

    app: CompiledApplication
    public_key_validator: PublicRouteKeyValidator | None = None
    now: datetime | None = None

    def build(
        self,
        session: RouteDeckSession,
        *,
        operation_id: str,
    ) -> OperationContextScope:
        validate_session_location(
            self.app,
            session,
            public_key_validator=self.public_key_validator,
            now=self.now,
        )
        node = self._current_node(session)
        operation = next(
            (
                candidate
                for candidate in node.operations
                if candidate.id == operation_id
            ),
            None,
        )
        if (
            operation is None
            or operation_id in session.public_state.disabled_operation_ids
        ):
            raise RouteDeckValidationError(
                f"Operation {operation_id!r} is not legal at node {node.id!r}"
            )

        declared_providers = {provider.id for provider in node.context_providers} | {
            provider.id for provider in node.entity_providers
        }
        provider_ids = tuple(
            provider.id
            for provider in operation.provider_refs
            if provider.id in declared_providers
        )
        if len(provider_ids) != len(operation.provider_refs):
            raise RouteDeckValidationError(
                f"Operation {operation_id!r} references a provider not declared "
                f"at node {node.id!r}"
            )

        entity_kinds = {provider.entity_kind for provider in node.entity_providers}
        allowed_bindings = {
            (binding.public_handle, binding.entity_kind)
            for binding in session.private_state.entity_bindings
            if operation_id in binding.allowed_operation_ids
            and binding.entity_kind in entity_kinds
        }
        entities = tuple(
            entity
            for entity in session.public_state.entity_handles
            if (entity.handle, entity.entity_kind) in allowed_bindings
        )

        return OperationContextScope(
            node_id=node.id,
            operation_id=operation_id,
            provider_ids=provider_ids,
            entities=entities,
        )

    def _current_node(self, session: RouteDeckSession) -> Node:
        try:
            return self.app.require_node(session.current.node_id)
        except RouteDeckValidationError as error:
            raise RouteDeckValidationError(
                f"Session references unknown node: {session.current.node_id}"
            ) from error


__all__ = ["ContextScopeBuilder"]
