from __future__ import annotations

from datetime import datetime

from ..app import CompiledRouteDeckApp
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.session import Location, RouteDeckSession
from ..state.session import require_compatible_session
from ..validation import RouteDeckValidationError
from .routes import PublicRouteKeyValidator


def validate_session_location(
    app: CompiledRouteDeckApp,
    session: RouteDeckSession,
    *,
    location: Location | None = None,
    public_key_validator: PublicRouteKeyValidator | None = None,
    now: datetime | None = None,
) -> None:
    """Validate one canonical location before context or public projection."""

    require_compatible_session(app, session)
    candidate = location or session.current
    node_id = candidate.node_id
    expected_names = set(app.routes.path_parameter_names(node_id))
    params = {parameter.name: parameter.value for parameter in candidate.route_params}
    if set(params) != expected_names:
        raise RouteDeckValidationError(
            f"Session route parameters do not match node {node_id!r}"
        )
    if app.routes.deep_link_policy(node_id) is DeepLinkPolicy.SHAREABLE:
        app.routes.validate_public_bindings(
            node_id,
            params,
            public_key_validator,
        )
        return
    if now is None or now.tzinfo is None:
        raise RouteDeckValidationError(
            "Session-bound location requires an aware injected clock"
        )
    if not any(
        capability.session_id == session.session_id
        and capability.node_id == node_id
        and capability.route_params == candidate.route_params
        and capability.expires_at > now
        for capability in session.private_state.resume_capabilities
    ):
        raise RouteDeckValidationError(
            "Session-bound location requires an exact active resume capability"
        )


__all__ = ["validate_session_location"]
