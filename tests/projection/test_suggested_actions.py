from __future__ import annotations

import pytest

from routedeck_core.app import Application, Feature, compile_app
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeRef,
    NodeKind,
    Route,
    Transition,
)
from routedeck_core.contracts.operations import (
    EntityProvider,
    Operation,
    OperationSource,
    SafetyClass,
)
from routedeck_core.contracts.projection import PublicEntityHandle
from routedeck_core.contracts.session import PrivateEntityBinding
from routedeck_core.contracts.suggestions import (
    SuggestedAction,
    SuggestedActionVisibility,
)
from routedeck_core.contracts.surfaces import SurfaceSlots
from routedeck_core.projection.projector import ProjectionProjector
from routedeck_testing.factories import session_factory
from routedeck_core.validation import RouteDeckValidationError


def _compiled_app(
    *,
    require_collection: bool = False,
    allowed_sources: frozenset[OperationSource] = frozenset(OperationSource),
):
    operation = Operation(
        id="test.browse",
        title="Browse tests",
        description="Load the current test collection.",
        safety_class=SafetyClass.READ_EXTERNAL,
        allowed_sources=allowed_sources,
        outcomes=("listed",),
    )
    node = Node(
        id="test.home",
        title="Test home",
        kind=NodeKind.SECTION,
        route=Route(template="/", deep_link_policy=DeepLinkPolicy.SHAREABLE),
        operations=(operation,),
        outgoing=(
            Transition(
                operation=operation.ref,
                outcome="listed",
                target=NodeRef(id="test.home"),
            ),
        ),
        entity_providers=(
            (
                EntityProvider(
                    id="test.collection",
                    entity_kind="collection",
                    description="Current test collection.",
                ),
            )
            if require_collection
            else ()
        ),
        surfaces=SurfaceSlots(active=None),
        suggested_actions=(
            SuggestedAction(
                id="test.browse_action",
                operation_id=operation.id,
                visibility=SuggestedActionVisibility(
                    required_entity_kinds=("collection",) if require_collection else ()
                ),
            ),
        ),
    )
    return compile_app(
        Application(
            name="suggested-action-test",
            entry_node=node.ref,
            features=(
                Feature(
                    namespace="test",
                    nodes=(node,),
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


def test_compiler_rejects_suggested_action_without_surface_source() -> None:
    with pytest.raises(RouteDeckValidationError, match="allow surface invocation"):
        _compiled_app(allowed_sources=frozenset({OperationSource.AGENT}))


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


def test_projection_shows_an_action_only_after_its_required_entity_is_bound() -> None:
    app = _compiled_app(require_collection=True)
    session = session_factory(app=app, node_id="test.home")

    assert ProjectionProjector(app).project(session).suggested_actions == ()

    session = session.model_copy(
        update={
            "private_state": session.private_state.model_copy(
                update={
                    "entity_bindings": (
                        PrivateEntityBinding(
                            entity_kind="collection",
                            public_handle="collection-handle",
                            private_id="collection-private-id",
                        ),
                    )
                }
            ),
            "public_state": session.public_state.model_copy(
                update={
                    "entity_handles": (
                        PublicEntityHandle(
                            entity_kind="collection",
                            handle="collection-handle",
                        ),
                    )
                }
            ),
        }
    )

    projection = ProjectionProjector(app).project(session)

    assert tuple(action.action_id for action in projection.suggested_actions) == (
        "test.browse_action",
    )
