from __future__ import annotations

from hashlib import sha256

from ..app.compiled import CompiledApplication
from ..contracts.session import (
    Location,
    PrivateSessionState,
    PublicSessionState,
    RouteDeckSession,
)
from ..validation import RouteDeckValidationError


SESSION_SCHEMA_VERSION = 4


def navgraph_version(app: CompiledApplication) -> str:
    document = app.contract_documents()["compiled-navgraph.json"].encode("utf-8")
    return sha256(document).hexdigest()


def create_session(
    *,
    app: CompiledApplication,
    session_id: str,
    private_state: PrivateSessionState,
    public_state: PublicSessionState | None = None,
) -> RouteDeckSession:
    return RouteDeckSession(
        session_id=session_id,
        schema_version=SESSION_SCHEMA_VERSION,
        navgraph_version=navgraph_version(app),
        session_version=1,
        projection_version=1,
        event_cursor=0,
        next_history_entry_id=2,
        current=Location(node_id=app.graph.entry_node.id, entry_id=1),
        private_state=private_state,
        public_state=(
            public_state if public_state is not None else PublicSessionState()
        ),
    )


def require_current_session(
    app: CompiledApplication,
    session: RouteDeckSession,
) -> None:
    """Reject state whose schema or compiled navgraph identity cannot be applied."""

    if session.schema_version != SESSION_SCHEMA_VERSION:
        raise RouteDeckValidationError("session_upgrade_required")
    if session.navgraph_version != navgraph_version(app):
        raise RouteDeckValidationError("session_upgrade_required")


__all__ = [
    "SESSION_SCHEMA_VERSION",
    "create_session",
    "navgraph_version",
    "require_current_session",
]
