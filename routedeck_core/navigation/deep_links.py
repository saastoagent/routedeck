from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from ..app import CompiledRouteDeckApp
from ..contracts.navigation import DeepLinkPolicy
from ..state.session import require_compatible_session
from .routes import (
    DecodedRoute,
    PublicRouteKeyValidator,
    RouteCapabilityMismatch,
    RouteResumeCapability,
    RouteSessionContext,
    RouteSessionRequired,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..contracts.session import RouteDeckSession


SessionRequired = RouteSessionRequired
CapabilityMismatch = RouteCapabilityMismatch


@dataclass(frozen=True)
class DeepLinkEngine:
    """Encode and open only routes declared by a compiled RouteDeck app."""

    app: CompiledRouteDeckApp

    def encode(
        self,
        node_id: str,
        params: Mapping[str, str],
        *,
        session: RouteDeckSession | None = None,
        now: datetime | None = None,
        public_key_validator: PublicRouteKeyValidator | None = None,
    ) -> str:
        if session is not None:
            require_compatible_session(self.app, session)
        path = self.app.routes.encode(node_id, params)
        if self.app.routes.deep_link_policy(node_id) is DeepLinkPolicy.SHAREABLE:
            self.app.routes.validate_public_bindings(
                node_id,
                params,
                public_key_validator,
            )
            return path
        if session is None or now is None:
            raise SessionRequired(
                "Session-bound link generation requires authenticated session context"
            )
        context = self._session_context(
            session=session,
            now=now,
            public_key_validator=None,
        )
        self.app.routes.decode(path, context)
        return path

    def open(
        self,
        path: str,
        *,
        session: RouteDeckSession | None,
        now: datetime,
        public_key_validator: PublicRouteKeyValidator | None = None,
    ) -> DecodedRoute:
        if session is not None:
            require_compatible_session(self.app, session)
        context = self._session_context(
            session=session,
            now=now,
            public_key_validator=public_key_validator,
        )
        return self.app.routes.decode(path, context)

    @staticmethod
    def _session_context(
        *,
        session: RouteDeckSession | None,
        now: datetime,
        public_key_validator: PublicRouteKeyValidator | None,
    ) -> RouteSessionContext | None:
        if session is None and public_key_validator is None:
            return None

        capabilities: tuple[RouteResumeCapability, ...] = ()
        if session is not None:
            capabilities = tuple(
                RouteResumeCapability(
                    handle=capability.handle,
                    session_id=capability.session_id,
                    node_id=capability.node_id,
                    expires_at=capability.expires_at,
                    route_params=capability.route_params,
                )
                for capability in session.private_state.resume_capabilities
            )

        return RouteSessionContext(
            guest_session_id=session.session_id if session is not None else None,
            public_key_validator=public_key_validator,
            resume_capabilities=capabilities,
            now=now,
        )


__all__ = [
    "CapabilityMismatch",
    "DeepLinkEngine",
    "SessionRequired",
]
