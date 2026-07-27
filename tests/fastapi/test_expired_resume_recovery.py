from datetime import UTC, datetime, timedelta

import pytest

from routedeck_core.app import Application, Feature, compile_app
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.navigation import DeepLinkPolicy, NodeKind, Route
from routedeck_core.contracts.session import ResumeCapabilityBinding
from routedeck_core.contracts.surfaces import SurfaceSlots
from routedeck_core.projection import ProjectionProjector
from routedeck_core.validation import RouteDeckValidationError
from routedeck_fastapi.responses import failure_for_exception
from routedeck_testing.factories import session_factory


NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def _compiled_app():
    node = Node(
        id="test.private",
        title="Private test node",
        kind=NodeKind.SECTION,
        route=Route(template="/private", deep_link_policy=DeepLinkPolicy.SESSION_BOUND),
        surfaces=SurfaceSlots(active=None),
    )
    return compile_app(
        Application(
            name="expired-resume-test",
            entry_node=node.ref,
            features=(Feature(namespace="test", nodes=(node,)),),
        )
    )


def test_expired_session_bound_projection_allows_terminal_bootstrap_recovery() -> None:
    app = _compiled_app()
    session = session_factory(
        app=app,
        session_id="expired-resume-session",
        node_id="test.private",
        resume_capabilities=(
            ResumeCapabilityBinding(
                handle="expired-resume-handle",
                session_id="expired-resume-session",
                node_id="test.private",
                expires_at=NOW - timedelta(seconds=1),
            ),
        ),
    )

    with pytest.raises(RouteDeckValidationError) as captured:
        ProjectionProjector(app, now=NOW).project(session)

    status, failure = failure_for_exception(captured.value)

    assert status == 410
    assert failure.code == "resume_capability_expired"
    assert failure.phase == "session_validation"
