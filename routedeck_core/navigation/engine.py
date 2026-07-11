from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from ..app import CompiledRouteDeckApp
from ..contracts.application import NodeSpec
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.session import Location, LocationParameter, RouteDeckSession
from ..state.session import require_compatible_session
from ..state.history import move_back, move_forward
from ..state.reducer import HistoryReplaced, NodeEntered, reduce_session
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
        self._node(node_id)
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
        return reduce_session(session, NodeEntered(location=location))

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
        return reduce_session(
            session,
            HistoryReplaced(
                current=history.current,
                back_stack=history.back_stack,
                forward_stack=history.forward_stack,
            ),
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
        return reduce_session(
            session,
            HistoryReplaced(
                current=history.current,
                back_stack=history.back_stack,
                forward_stack=history.forward_stack,
            ),
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
            return reduce_session(
                session,
                HistoryReplaced(
                    current=history.current,
                    back_stack=history.back_stack,
                    forward_stack=history.forward_stack,
                ),
            )
        return self.open(
            session,
            node_id=target.id,
            public_key_validator=public_key_validator,
            resume_handle=resume_handle,
            now=now,
        )

    def _node(self, node_id: str) -> NodeSpec:
        node = next(
            (candidate for candidate in self.app.spec.nodes if candidate.id == node_id),
            None,
        )
        if node is None:
            raise RouteDeckValidationError(f"Unknown navigation node: {node_id}")
        return node


__all__ = ["NavigationEngine"]
