from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..app import CompiledRouteDeckApp
from ..contracts.application import NodeSpec
from ..contracts.projection import (
    FrozenJson,
    ProjectedNavigation,
    ProjectedOperation,
    ProjectedSurface,
    ProjectedSurfaceSlots,
    ProjectionDiagnostics,
    ProjectionLocation,
    ProjectionStatus,
    PublicEntityHandle,
    PublicProjection,
    PublicValue,
)
from ..contracts.session import PublicSurfaceState, RouteDeckSession
from ..contracts.surfaces import SurfaceSpec
from ..navigation.routes import PublicRouteKeyValidator
from ..validation import RouteDeckValidationError
from .redaction import project_public_values
from ..navigation.session_location import validate_session_location


@dataclass(frozen=True)
class ProjectionProjector:
    """Derive the complete public view from one canonical RouteDeck session."""

    app: CompiledRouteDeckApp
    public_key_validator: PublicRouteKeyValidator | None = None
    now: datetime | None = None

    def project(self, session: RouteDeckSession) -> PublicProjection:
        validate_session_location(
            self.app,
            session,
            public_key_validator=self.public_key_validator,
            now=self.now,
        )
        for history_location in session.back_stack[-1:] + session.forward_stack[-1:]:
            validate_session_location(
                self.app,
                session,
                location=history_location,
                public_key_validator=self.public_key_validator,
                now=self.now,
            )
        node = self._current_node(session)
        legal_operations = tuple(
            operation
            for operation in node.operations
            if operation.id not in session.public_state.disabled_operation_ids
        )
        legal_operation_ids = {operation.id for operation in legal_operations}
        visible_handles = self._visible_handles(
            session,
            legal_operation_ids,
            {provider.entity_kind for provider in node.entity_providers},
        )
        route_parameter_names = set(self.app.routes.path_parameter_names(node.id))
        projection_location = ProjectionLocation(
            node_id=node.id,
            route_params=tuple(
                PublicValue(
                    name=parameter.name,
                    value=FrozenJson(parameter.value),
                )
                for parameter in session.current.route_params
                if parameter.name in route_parameter_names
            ),
        )
        surface_ids = tuple(
            state.surface_id for state in session.public_state.surface_state
        )
        declared_surface_ids = {
            surface.id for surface in node.surfaces.declared_surfaces()
        }
        if len(surface_ids) != len(set(surface_ids)):
            raise RouteDeckValidationError(
                f"Session contains duplicate surface state at node {node.id!r}"
            )
        undeclared_surface_ids = set(surface_ids) - declared_surface_ids
        if undeclared_surface_ids:
            raise RouteDeckValidationError(
                f"Session contains undeclared surface state at node {node.id!r}: "
                f"{sorted(undeclared_surface_ids)!r}"
            )
        surface_state = {
            state.surface_id: state for state in session.public_state.surface_state
        }

        return PublicProjection(
            session_version=session.session_version,
            projection_version=session.projection_version,
            event_cursor=session.event_cursor,
            current=projection_location,
            navigation=ProjectedNavigation(
                current=projection_location,
                route_template=node.route.template,
                can_back=node.navigation.can_back and bool(session.back_stack),
                can_forward=(
                    node.navigation.can_forward and bool(session.forward_stack)
                ),
                can_cancel=(
                    node.navigation.can_cancel
                    and (
                        node.navigation.cancel_target is not None
                        or bool(session.back_stack)
                    )
                ),
                back_node_id=(
                    session.back_stack[-1].node_id if session.back_stack else None
                ),
                forward_node_id=(
                    session.forward_stack[-1].node_id if session.forward_stack else None
                ),
                cancel_target_node_id=(
                    node.navigation.cancel_target.id
                    if node.navigation.cancel_target is not None
                    else None
                ),
            ),
            legal_operations=tuple(
                ProjectedOperation(
                    operation_id=operation.id,
                    title=operation.title,
                    safety_class=operation.safety_class.value,
                    review_required=operation.review_policy.value == "required",
                )
                for operation in legal_operations
            ),
            entities=visible_handles,
            surfaces=self._surface_slots(node, surface_state),
            status=ProjectionStatus(
                code=session.public_state.status_code,
                message=session.public_state.status_message,
            ),
            failure=session.public_state.failure,
            diagnostics=ProjectionDiagnostics(
                schema_version=session.schema_version,
                navgraph_version=session.navgraph_version,
                current_node_id=node.id,
                declared_provider_ids=tuple(
                    provider.id for provider in node.context_providers
                )
                + tuple(provider.id for provider in node.entity_providers),
            ),
        )

    @staticmethod
    def _visible_handles(
        session: RouteDeckSession,
        legal_operation_ids: set[str],
        declared_entity_kinds: set[str],
    ) -> tuple[PublicEntityHandle, ...]:
        allowed_bindings = {
            (binding.public_handle, binding.entity_kind)
            for binding in session.private_state.entity_bindings
            if legal_operation_ids.intersection(binding.allowed_operation_ids)
            and binding.entity_kind in declared_entity_kinds
        }
        return tuple(
            entity
            for entity in session.public_state.entity_handles
            if (entity.handle, entity.entity_kind) in allowed_bindings
        )

    @staticmethod
    def _project_surface(
        surface: SurfaceSpec,
        state: PublicSurfaceState | None,
    ) -> ProjectedSurface:
        return ProjectedSurface(
            surface_id=surface.id,
            component=surface.component,
            props=project_public_values(
                state.values if state is not None else (),
                schema=surface.public_props_schema_value(),
            ),
        )

    def _surface_slots(
        self,
        node: NodeSpec,
        state: dict[str, PublicSurfaceState],
    ) -> ProjectedSurfaceSlots:
        def project(surface: SurfaceSpec) -> ProjectedSurface:
            return self._project_surface(surface, state.get(surface.id))

        surfaces = node.surfaces
        return ProjectedSurfaceSlots(
            active=project(surfaces.active),
            frame=tuple(project(surface) for surface in surfaces.frame),
            peer=tuple(project(surface) for surface in surfaces.peer),
            detail=tuple(project(surface) for surface in surfaces.detail),
            form=tuple(project(surface) for surface in surfaces.form),
            review=tuple(project(surface) for surface in surfaces.review),
            status=tuple(project(surface) for surface in surfaces.status),
            error=tuple(project(surface) for surface in surfaces.error),
            diagnostic=tuple(project(surface) for surface in surfaces.diagnostic),
        )

    def _current_node(self, session: RouteDeckSession) -> NodeSpec:
        node = next(
            (
                candidate
                for candidate in self.app.spec.nodes
                if candidate.id == session.current.node_id
            ),
            None,
        )
        if node is None:
            raise RouteDeckValidationError(
                f"Session references unknown node: {session.current.node_id}"
            )
        return node


__all__ = ["ProjectionProjector"]
