"""Canonical immutable RouteDeck session-state APIs."""

from .leases import ExecutionClaim, TurnClaim, TurnLease, TurnOwnerKind
from .reducer import (
    NodeEntered,
    PrivateDraftStored,
    PrivateSessionStateStored,
    PublicEventsRecorded,
    PublicSessionStateStored,
    reduce_session,
    reduce_session_batch,
)
from .session import create_session, navgraph_version, require_compatible_session

__all__ = [
    "ExecutionClaim",
    "NodeEntered",
    "PrivateDraftStored",
    "PrivateSessionStateStored",
    "PublicEventsRecorded",
    "PublicSessionStateStored",
    "TurnClaim",
    "TurnLease",
    "TurnOwnerKind",
    "create_session",
    "navgraph_version",
    "reduce_session",
    "reduce_session_batch",
    "require_compatible_session",
]
