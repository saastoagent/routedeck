from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..app import CompiledRouteDeckApp
from ..contracts.application import NodeSpec
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.projection import (
    FrozenJson,
    ProjectedNavigation,
    ProjectedOperation,
    ProjectedSuggestedAction,
    ProjectedSurface,
    ProjectedSurfaceSlots,
    ProjectionDiagnostics,
    ProjectionLocation,
    ProjectionStatus,
    PublicProjection,
    PublicValue,
)
from ..contracts.session import (
    PublicSurfaceState,
    ReviewResolution,
    RouteDeckSession,
)
from ..contracts.surfaces import SurfaceSpec
from ..navigation.routes import PublicRouteKeyValidator
from ..navigation.session_location import validate_session_location
from ..state.surfaces import validate_canonical_surface_state
from ..validation import RouteDeckValidationError
from .policy import (
    resolve_projection_mode,
    visible_entity_handles,
    visible_suggested_actions,
)
from .redaction import project_public_values


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
        mode = resolve_projection_mode(self.app, node, session)
        legal_operations = mode.legal_operations
        legal_operation_ids = {operation.id for operation in legal_operations}
        legal_operation_by_id = {
            operation.id: operation for operation in legal_operations
        }
        suggested_actions = visible_suggested_actions(
            node,
            session,
            legal_operation_ids,
        )
        visible_handles = visible_entity_handles(
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
        validate_canonical_surface_state(
            self.app,
            session.public_state.surface_state,
        )
        declared_surface_ids = {
            surface.id for surface in node.surfaces.declared_surfaces()
        }
        surface_state = {
            state.surface_id: state
            for state in session.public_state.surface_state
            if state.surface_id in declared_surface_ids
        }

        return PublicProjection(
            session_version=session.session_version,
            projection_version=session.projection_version,
            event_cursor=session.event_cursor,
            current=projection_location,
            navigation=ProjectedNavigation(
                current=projection_location,
                current_entry_id=self._current_entry_id(session),
                route_template=node.route.template,
                resume_handle=self._current_resume_handle(session, node),
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
            suggested_actions=tuple(
                ProjectedSuggestedAction(
                    action_id=action.id,
                    label=action.label or legal_operation_by_id[action.operation_id].title,
                    operation_id=action.operation_id,
                    arguments=action.arguments,
                )
                for action in suggested_actions
            ),
            entities=visible_handles,
            surfaces=self._surface_slots(
                node,
                surface_state,
                active_surface=mode.active_surface,
                review_active=(
                    session.operation is not None
                    and session.operation.pending_review is not None
                    and session.operation.pending_review.resolution
                    is ReviewResolution.PENDING
                ),
            ),
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
    def _current_entry_id(session: RouteDeckSession) -> int:
        if session.current.entry_id is None:
            raise RouteDeckValidationError(
                "Canonical current location requires a history entry ID"
            )
        return session.current.entry_id

    def _current_resume_handle(
        self,
        session: RouteDeckSession,
        node: NodeSpec,
    ) -> str | None:
        if node.route.deep_link_policy is DeepLinkPolicy.SHAREABLE:
            return None
        if self.now is None or self.now.tzinfo is None:
            raise RouteDeckValidationError(
                "Session-bound projection requires an aware injected clock"
            )
        matches = tuple(
            capability
            for capability in session.private_state.resume_capabilities
            if capability.session_id == session.session_id
            and capability.node_id == session.current.node_id
            and capability.route_params == session.current.route_params
            and capability.expires_at > self.now
        )
        if len(matches) != 1:
            raise RouteDeckValidationError(
                "Session-bound projection requires exactly one current resume capability"
            )
        return matches[0].handle

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
        *,
        active_surface: SurfaceSpec | None,
        review_active: bool,
    ) -> ProjectedSurfaceSlots:
        def project(surface: SurfaceSpec) -> ProjectedSurface:
            return self._project_surface(surface, state.get(surface.id))

        surfaces = node.surfaces
        return ProjectedSurfaceSlots(
            active=project(active_surface) if active_surface is not None else None,
            frame=tuple(project(surface) for surface in surfaces.frame),
            peer=tuple(project(surface) for surface in surfaces.peer),
            detail=tuple(project(surface) for surface in surfaces.detail),
            form=tuple(project(surface) for surface in surfaces.form),
            review=tuple(
                self._project_surface(
                    surface,
                    state.get(surface.id) if review_active else None,
                )
                for surface in surfaces.review
            ),
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
