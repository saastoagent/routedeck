from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from ..app import CompiledRouteDeckApp
from ..contracts.application import NodeSpec
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.session import Location, LocationParameter, RouteDeckSession
from ..state.aggregate import RouteDeckSessionAggregate
from ..state.history import move_back, move_forward
from ..state.session import require_compatible_session
from ..state.surfaces import surface_state_for_node
from ..validation import RouteDeckValidationError
from .deep_links import DeepLinkEngine
from .routes import PublicRouteKeyValidator, RouteCapabilityMismatch
from .session_location import validate_session_location


@dataclass(frozen=True)
class NavigationEngine:
    """Apply compiled navigation policy to immutable RouteDeck sessions."""

    app: CompiledRouteDeckApp

    def open(
        self,
        session: RouteDeckSession,
        *,
        node_id: str,
        route_params: Mapping[str, str] | None = None,
        public_key_validator: PublicRouteKeyValidator | None = None,
        resume_handle: str | None = None,
        now: datetime | None = None,
    ) -> RouteDeckSession:
        require_compatible_session(self.app, session)
        validate_session_location(
            self.app,
            session,
            public_key_validator=public_key_validator,
            now=now,
        )
        target_node = self._node(node_id)
        declared_names = self.app.routes.path_parameter_names(node_id)
        supplied = dict(route_params or {})
        if set(supplied) != set(declared_names):
            raise RouteDeckValidationError(
                f"Node {node_id!r} requires route parameters "
                f"{sorted(declared_names)!r}; received {sorted(supplied)!r}"
            )
        deep_link_policy = self.app.routes.deep_link_policy(node_id)
        if deep_link_policy is DeepLinkPolicy.SHAREABLE:
            self.app.routes.validate_public_bindings(
                node_id,
                supplied,
                public_key_validator,
            )
        else:
            if not resume_handle or now is None:
                raise RouteCapabilityMismatch(
                    "Session-bound navigation requires a resume capability and clock"
                )
            DeepLinkEngine(self.app).encode(
                node_id,
                {**supplied, "resume_handle": resume_handle},
                session=session,
                now=now,
            )
        location = Location(
            node_id=node_id,
            route_params=tuple(
                LocationParameter(name=name, value=supplied[name])
                for name in declared_names
            ),
        )
        return self._enter_location(session, location, target_node)

    def back(
        self,
        session: RouteDeckSession,
        *,
        public_key_validator: PublicRouteKeyValidator | None = None,
        now: datetime | None = None,
    ) -> RouteDeckSession:
        require_compatible_session(self.app, session)
        validate_session_location(
            self.app,
            session,
            public_key_validator=public_key_validator,
            now=now,
        )
        node = self._node(session.current.node_id)
        if not node.navigation.can_back:
            raise RouteDeckValidationError(
                f"Back navigation is disabled at node {node.id!r}"
            )
        if not session.back_stack:
            return session
        history = move_back(
            current=session.current,
            back_stack=session.back_stack,
            forward_stack=session.forward_stack,
        )
        validate_session_location(
            self.app,
            session,
            location=history.current,
            public_key_validator=public_key_validator,
            now=now,
        )
        return self._replace_history(
            session,
            current=history.current,
            back_stack=history.back_stack,
            forward_stack=history.forward_stack,
            target_node=self._node(history.current.node_id),
        )

    def forward(
        self,
        session: RouteDeckSession,
        *,
        public_key_validator: PublicRouteKeyValidator | None = None,
        now: datetime | None = None,
    ) -> RouteDeckSession:
        require_compatible_session(self.app, session)
        validate_session_location(
            self.app,
            session,
            public_key_validator=public_key_validator,
            now=now,
        )
        node = self._node(session.current.node_id)
        if not node.navigation.can_forward:
            raise RouteDeckValidationError(
                f"Forward navigation is disabled at node {node.id!r}"
            )
        if not session.forward_stack:
            return session
        history = move_forward(
            current=session.current,
            back_stack=session.back_stack,
            forward_stack=session.forward_stack,
        )
        validate_session_location(
            self.app,
            session,
            location=history.current,
            public_key_validator=public_key_validator,
            now=now,
        )
        return self._replace_history(
            session,
            current=history.current,
            back_stack=history.back_stack,
            forward_stack=history.forward_stack,
            target_node=self._node(history.current.node_id),
        )

    def cancel(
        self,
        session: RouteDeckSession,
        *,
        public_key_validator: PublicRouteKeyValidator | None = None,
        resume_handle: str | None = None,
        now: datetime | None = None,
    ) -> RouteDeckSession:
        require_compatible_session(self.app, session)
        validate_session_location(
            self.app,
            session,
            public_key_validator=public_key_validator,
            now=now,
        )
        node = self._node(session.current.node_id)
        target = node.navigation.cancel_target
        if not node.navigation.can_cancel:
            raise RouteDeckValidationError(
                f"Cancel navigation is not declared at node {node.id!r}"
            )
        if target is None:
            if not session.back_stack:
                return session
            history = move_back(
                current=session.current,
                back_stack=session.back_stack,
                forward_stack=session.forward_stack,
            )
            validate_session_location(
                self.app,
                session,
                location=history.current,
                public_key_validator=public_key_validator,
                now=now,
            )
            return self._replace_history(
                session,
                current=history.current,
                back_stack=history.back_stack,
                forward_stack=history.forward_stack,
                target_node=self._node(history.current.node_id),
            )
        return self.open(
            session,
            node_id=target.id,
            public_key_validator=public_key_validator,
            resume_handle=resume_handle,
            now=now,
        )

    def restore_history_entry(
        self,
        session: RouteDeckSession,
        entry_id: int,
        *,
        public_key_validator: PublicRouteKeyValidator | None = None,
        now: datetime | None = None,
    ) -> RouteDeckSession:
        """Restore one exact canonical history entry without inferring direction."""

        require_compatible_session(self.app, session)
        validate_session_location(
            self.app,
            session,
            public_key_validator=public_key_validator,
            now=now,
        )
        if isinstance(entry_id, bool) or not isinstance(entry_id, int) or entry_id < 1:
            raise RouteDeckValidationError("Canonical history entry ID is invalid")
        timeline = (
            *session.back_stack,
            session.current,
            *reversed(session.forward_stack),
        )
        entry_ids = tuple(location.entry_id for location in timeline)
        if any(candidate is None for candidate in entry_ids) or len(entry_ids) != len(
            set(entry_ids)
        ):
            raise RouteDeckValidationError(
                "Canonical history contains missing or duplicate entry IDs"
            )
        matching_indices = tuple(
            index
            for index, location in enumerate(timeline)
            if location.entry_id == entry_id
        )
        if len(matching_indices) != 1:
            raise RouteDeckValidationError(
                f"Canonical history entry {entry_id!r} does not exist"
            )
        target_index = matching_indices[0]
        if timeline[target_index] == session.current:
            return session
        target = timeline[target_index]
        validate_session_location(
            self.app,
            session,
            location=target,
            public_key_validator=public_key_validator,
            now=now,
        )
        return self._replace_history(
            session,
            current=target,
            back_stack=tuple(timeline[:target_index]),
            forward_stack=tuple(reversed(timeline[target_index + 1 :])),
            target_node=self._node(target.node_id),
        )

    def _enter_location(
        self,
        session: RouteDeckSession,
        location: Location,
        target_node: NodeSpec,
    ) -> RouteDeckSession:
        aggregate = RouteDeckSessionAggregate(session).enter_node(location)
        return self._retain_surface_state(aggregate, session, target_node)

    def _replace_history(
        self,
        session: RouteDeckSession,
        *,
        current: Location,
        back_stack: tuple[Location, ...],
        forward_stack: tuple[Location, ...],
        target_node: NodeSpec,
    ) -> RouteDeckSession:
        aggregate = RouteDeckSessionAggregate(session).replace_history(
            current=current,
            back_stack=back_stack,
            forward_stack=forward_stack,
        )
        return self._retain_surface_state(aggregate, session, target_node)

    def _retain_surface_state(
        self,
        aggregate: RouteDeckSessionAggregate,
        session: RouteDeckSession,
        target_node: NodeSpec,
    ) -> RouteDeckSession:
        retained_surface_state = surface_state_for_node(
            self.app,
            session.public_state.surface_state,
            target_node,
        )
        public_state = session.public_state.model_copy(
            update={"surface_state": retained_surface_state}
        )
        return aggregate.set_public_state(public_state).commit()

    def _node(self, node_id: str) -> NodeSpec:
        node = next(
            (candidate for candidate in self.app.spec.nodes if candidate.id == node_id),
            None,
        )
        if node is None:
            raise RouteDeckValidationError(f"Unknown navigation node: {node_id}")
        return node


__all__ = ["NavigationEngine"]
