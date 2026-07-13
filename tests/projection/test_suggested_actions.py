from __future__ import annotations

from routedeck_core.app import ApplicationSpec, FeatureSpec, compile_app
from routedeck_core.contracts.application import NodeSpec
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeKind,
    RouteSpec,
    TransitionSpec,
)
from routedeck_core.contracts.operations import OperationSpec, SafetyClass
from routedeck_core.contracts.suggestions import SuggestedActionSpec
from routedeck_core.contracts.surfaces import SurfaceSlotsSpec
from routedeck_core.projection.projector import ProjectionProjector
from routedeck_testing.factories import session_factory


def _compiled_app():
    operation = OperationSpec(
        id="test.browse",
        title="Browse tests",
        description="Load the current test collection.",
        safety_class=SafetyClass.READ_EXTERNAL,
        outcomes=("listed",),
    )
    node = NodeSpec(
        id="test.home",
        title="Test home",
        kind=NodeKind.SECTION,
        route=RouteSpec(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(operation,),
        surfaces=SurfaceSlotsSpec(active=None),
        suggested_actions=(
            SuggestedActionSpec(
                id="test.browse_action",
                operation_id=operation.id,
            ),
        ),
    )
    return compile_app(
        ApplicationSpec(
            name="suggested-action-test",
            entry_node=node.ref,
            features=(
                FeatureSpec(
                    namespace="test",
                    nodes=(node,),
                    transitions=(
                        TransitionSpec(
                            source=node.ref,
                            operation=operation.ref,
                            outcome="listed",
                            target=node.ref,
                        ),
                    ),
                ),
            ),
        )
    )


def test_projection_emits_declared_actions_with_operation_titles() -> None:
    app = _compiled_app()

    projection = ProjectionProjector(app).project(
        session_factory(app=app, node_id="test.home")
    )

    assert projection.surfaces.active is None
    assert [action.model_dump(mode="json") for action in projection.suggested_actions] == [
        {
            "action_id": "test.browse_action",
            "label": "Browse tests",
            "operation_id": "test.browse",
            "arguments": {},
        }
    ]


def test_projection_hides_an_action_when_its_operation_is_not_legal() -> None:
    app = _compiled_app()
    session = session_factory(app=app, node_id="test.home")
    session = session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={"disabled_operation_ids": ("test.browse",)}
            )
        }
    )

    projection = ProjectionProjector(app).project(session)

    assert projection.legal_operations == ()
    assert projection.suggested_actions == ()
