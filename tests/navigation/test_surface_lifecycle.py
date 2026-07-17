from __future__ import annotations

import pytest

from routedeck_core.app import Application, Feature, compile_app
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    Route,
    Transition,
)
from routedeck_core.contracts.operations import Operation, SafetyClass
from routedeck_core.contracts.session import PublicSurfaceState
from routedeck_core.contracts.surfaces import (
    SurfaceLifecycle,
    SurfaceSlots,
    Surface,
)
from routedeck_core.navigation.engine import NavigationEngine
from routedeck_core.projection.projector import ProjectionProjector
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import session_factory


def _lifecycle_app(*, share_ephemeral_with_target: bool = False):
    stable = Surface(
        id="flow.stable",
        component="flow.stable",
        lifecycle=SurfaceLifecycle.STABLE,
    )
    ephemeral = Surface(
        id="flow.ephemeral",
        component="flow.ephemeral",
        lifecycle=SurfaceLifecycle.EPHEMERAL,
    )
    end_surface = Surface(id="flow.end", component="flow.end")
    advance = Operation(
        id="flow.advance",
        title="Advance",
        description="Advance the test flow.",
        safety_class=SafetyClass.NAVIGATION,
        outcomes=("advanced",),
    )
    start = Node(
        id="flow.start",
        title="Start",
        kind=NodeKind.WORKFLOW,
        route=Route(
            template="/",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        operations=(advance,),
        surfaces=SurfaceSlots(
            active=ephemeral,
            frame=(stable,),
        ),
    )
    end = Node(
        id="flow.end",
        title="End",
        kind=NodeKind.WORKFLOW,
        route=Route(
            template="/end",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        surfaces=SurfaceSlots(
            active=end_surface,
            frame=(ephemeral,) if share_ephemeral_with_target else (),
        ),
    )
    start = start.model_copy(
        update={
            "outgoing": (
                Transition(
                    operation=advance.ref,
                    outcome="advanced",
                    target=end.ref,
                ),
            )
        }
    )
    return compile_app(
        Application(
            name="surface-lifecycle-test",
            entry_node=start.ref,
            features=(
                Feature(
                    namespace="flow",
                    nodes=(start, end),
                ),
            ),
        )
    )


def _session_with_surface_state(app):
    session = session_factory(app=app, node_id="flow.start")
    return session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={
                    "surface_state": (
                        PublicSurfaceState(surface_id="flow.stable"),
                        PublicSurfaceState(surface_id="flow.ephemeral"),
                    )
                }
            )
        }
    )


def test_navigation_retains_stable_and_drops_inactive_ephemeral_surface_state() -> None:
    app = _lifecycle_app()

    navigated = NavigationEngine(app).open(
        _session_with_surface_state(app),
        node_id="flow.end",
    )

    assert tuple(
        surface.surface_id for surface in navigated.public_state.surface_state
    ) == ("flow.stable",)
    projection_json = ProjectionProjector(app).project(navigated).model_dump_json()
    assert "flow.stable" not in projection_json
    assert "flow.ephemeral" not in projection_json


def test_navigation_keeps_ephemeral_state_while_target_still_declares_surface() -> None:
    app = _lifecycle_app(share_ephemeral_with_target=True)

    navigated = NavigationEngine(app).open(
        _session_with_surface_state(app),
        node_id="flow.end",
    )

    assert tuple(
        surface.surface_id for surface in navigated.public_state.surface_state
    ) == ("flow.stable", "flow.ephemeral")
    projection = ProjectionProjector(app).project(navigated)
    assert tuple(surface.surface_id for surface in projection.surfaces.frame) == (
        "flow.ephemeral",
    )


def test_projection_rejects_only_globally_unknown_canonical_surface_state() -> None:
    app = _lifecycle_app()
    session = NavigationEngine(app).open(
        _session_with_surface_state(app),
        node_id="flow.end",
    )
    invalid = session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={
                    "surface_state": (
                        *session.public_state.surface_state,
                        PublicSurfaceState(surface_id="flow.unknown"),
                    )
                }
            )
        }
    )

    with pytest.raises(RouteDeckValidationError, match="unknown canonical surface"):
        ProjectionProjector(app).project(invalid)
