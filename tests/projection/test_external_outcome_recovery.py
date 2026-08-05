from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from routedeck_core.app import Application, Feature, compile_app
from routedeck_core.app.compiled import CompiledApplication
from routedeck_core.contracts.application import Node
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.navigation import (
    DeepLinkPolicy,
    NodeRef,
    NodeKind,
    RecoveryPolicy,
    Route,
    Transition,
)
from routedeck_core.contracts.operations import (
    OperationRef,
    Operation,
    OperationSource,
    SafetyClass,
)
from routedeck_core.contracts.projection import PublicEntityHandle
from routedeck_core.contracts.session import (
    PrivateEntityBinding,
    ResumeCapabilityBinding,
    RouteDeckSession,
)
from routedeck_core.contracts.surfaces import SurfaceSlots, Surface
from routedeck_core.projection.projector import ProjectionProjector
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import session_factory


_ACTIVE_SURFACE = Surface(
    id="recovery.normal",
    component="recovery.normal",
)
_FAILURE_SURFACE = Surface(
    id="recovery.external_outcome_unknown",
    component="recovery.external_outcome_unknown",
)
_RECONCILE = Operation(
    id="recovery.reconcile",
    title="Reconcile",
    description="Resolve an explicitly unknown external outcome.",
    safety_class=SafetyClass.READ_EXTERNAL,
    allowed_sources=frozenset(OperationSource),
    outcomes=("reconciled",),
)
_UNRELATED_UNSAFE = Operation(
    id="recovery.delete_unrelated",
    title="Delete unrelated resource",
    description="An unsafe operation that must not leak into recovery projection.",
    safety_class=SafetyClass.DESTRUCTIVE,
    allowed_sources=frozenset(OperationSource),
    outcomes=("deleted",),
)


def _submit_operation(
    *,
    recovery_refs: tuple[OperationRef, ...] = (_RECONCILE.ref,),
) -> Operation:
    return Operation(
        id="recovery.submit",
        title="Submit",
        description="Perform one externally mutating request.",
        safety_class=SafetyClass.WRITE_EXTERNAL,
        allowed_sources=frozenset(OperationSource),
        outcomes=("submitted",),
        unknown_recovery_directive="reconcile_external_outcome",
        unknown_recovery_operation_refs=recovery_refs,
    )


def _recovery_app(
    *,
    recovery_refs: tuple[OperationRef, ...] = (_RECONCILE.ref,),
) -> CompiledApplication:
    submit = _submit_operation(recovery_refs=recovery_refs)
    node = Node(
        id="recovery.node",
        title="Recovery",
        kind=NodeKind.WORKFLOW,
        route=Route(
            template="/recovery",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        operations=(submit, _RECONCILE, _UNRELATED_UNSAFE),
        outgoing=(
            Transition(
                operation=submit.ref,
                outcome="submitted",
                target=NodeRef(id="recovery.node"),
            ),
            Transition(
                operation=_RECONCILE.ref,
                outcome="reconciled",
                target=NodeRef(id="recovery.node"),
            ),
            Transition(
                operation=_UNRELATED_UNSAFE.ref,
                outcome="deleted",
                target=NodeRef(id="recovery.node"),
            ),
        ),
        surfaces=SurfaceSlots(
            active=_ACTIVE_SURFACE,
            error=(_FAILURE_SURFACE,),
        ),
        recovery=RecoveryPolicy(
            directives=("reconcile_external_outcome",),
            failure_surface=_FAILURE_SURFACE.ref,
        ),
    )
    return compile_app(
        Application(
            name="recovery-projection-test",
            entry_node=node.ref,
            features=(
                Feature(
                    namespace="recovery",
                    nodes=(node,),
                ),
            ),
        )
    )


def _failure(
    *,
    operation_id: str | None = "recovery.submit",
    recovery_directive: str | None = "reconcile_external_outcome",
) -> RouteDeckFailure:
    return RouteDeckFailure(
        kind=FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
        code="external_outcome_unknown",
        phase="execution_recovery",
        correlation_id="correlation-1",
        operation_id=operation_id,
        request_id="request-1",
        public_message="The external outcome must be reconciled.",
        recovery_directive=recovery_directive,
    )


def _session(
    app: CompiledApplication,
    *,
    failure: RouteDeckFailure | None = None,
    disabled_operation_ids: tuple[str, ...] = (),
    node_id: str = "recovery.node",
) -> RouteDeckSession:
    session = session_factory(app=app, node_id=node_id)
    return session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={
                    "failure": failure,
                    "disabled_operation_ids": disabled_operation_ids,
                }
            )
        }
    )


def test_unknown_outcome_uses_dedicated_surface_and_only_declared_operation() -> None:
    app = _recovery_app()

    projection = ProjectionProjector(app).project(_session(app, failure=_failure()))

    assert projection.surfaces.active.surface_id == _FAILURE_SURFACE.id
    assert projection.surfaces.active.component == _FAILURE_SURFACE.component
    assert projection.legal_operation_ids == (_RECONCILE.id,)
    assert _UNRELATED_UNSAFE.id not in projection.legal_operation_ids
    assert "recovery.submit" not in projection.legal_operation_ids
    assert projection.failure is not None
    assert projection.failure.recovery_directive == "reconcile_external_outcome"


def test_unknown_outcome_respects_disabled_recovery_operations() -> None:
    app = _recovery_app()

    projection = ProjectionProjector(app).project(
        _session(
            app,
            failure=_failure(),
            disabled_operation_ids=(_RECONCILE.id,),
        )
    )

    assert projection.legal_operations == ()
    assert projection.surfaces.active.surface_id == _FAILURE_SURFACE.id


def test_unknown_outcome_without_operation_refs_exposes_only_typed_directive() -> None:
    app = _recovery_app(recovery_refs=())

    projection = ProjectionProjector(app).project(_session(app, failure=_failure()))

    assert projection.legal_operations == ()
    assert projection.surfaces.active.surface_id == _FAILURE_SURFACE.id
    assert projection.failure is not None
    assert projection.failure.recovery_directive == "reconcile_external_outcome"


@pytest.mark.parametrize(
    "failure",
    (
        _failure(operation_id=None),
        _failure(operation_id="recovery.missing"),
        _failure(recovery_directive=None),
        _failure(recovery_directive="retry_instead"),
    ),
)
def test_unknown_outcome_rejects_missing_or_mismatched_failure_identity(
    failure: RouteDeckFailure,
) -> None:
    app = _recovery_app()

    with pytest.raises(RouteDeckValidationError):
        ProjectionProjector(app).project(_session(app, failure=failure))


def test_unknown_outcome_rejects_recovery_operation_not_declared_at_node() -> None:
    app = _recovery_app()
    node = app.graph.nodes[0]
    forged_submit = _submit_operation(
        recovery_refs=(OperationRef(id="recovery.not_at_current_node"),)
    )
    forged_node = node.model_copy(
        update={
            "operations": (
                forged_submit,
                *tuple(
                    operation
                    for operation in node.operations
                    if operation.id != forged_submit.id
                ),
            )
        }
    )
    forged_app = replace(
        app,
        graph=app.graph.model_copy(update={"nodes": (forged_node,)}),
        nodes={forged_node.id: forged_node},
        operations={**app.operations, forged_submit.id: forged_submit},
    )

    with pytest.raises(RouteDeckValidationError):
        ProjectionProjector(forged_app).project(
            _session(forged_app, failure=_failure())
        )


@pytest.mark.parametrize(
    "forgery",
    (
        "submit_not_canonical",
        "directive_not_declared",
        "failure_surface_missing",
        "recovery_operation_not_canonical",
    ),
)
def test_unknown_outcome_rejects_forged_compiled_recovery_contract(
    forgery: str,
) -> None:
    app = _recovery_app()
    node = app.graph.nodes[0]
    operations = node.operations

    if forgery == "submit_not_canonical":
        forged_submit = operations[0].model_copy(update={"title": "Forged submit"})
        forged_node = node.model_copy(
            update={"operations": (forged_submit, *operations[1:])}
        )
    elif forgery == "directive_not_declared":
        forged_node = node.model_copy(
            update={"recovery": node.recovery.model_copy(update={"directives": ()})}
        )
    elif forgery == "failure_surface_missing":
        forged_node = node.model_copy(
            update={
                "recovery": node.recovery.model_copy(update={"failure_surface": None})
            }
        )
    else:
        forged_recovery = operations[1].model_copy(update={"title": "Forged reconcile"})
        forged_node = node.model_copy(
            update={
                "operations": (
                    operations[0],
                    forged_recovery,
                    *operations[2:],
                )
            }
        )

    forged_app = replace(
        app,
        graph=app.graph.model_copy(update={"nodes": (forged_node,)}),
        nodes={forged_node.id: forged_node},
    )

    with pytest.raises(RouteDeckValidationError):
        ProjectionProjector(forged_app).project(
            _session(forged_app, failure=_failure())
        )


def test_medusa_checkout_unknown_outcome_hides_recovery_without_order_binding() -> None:
    from medusa_agent.composition import compile_medusa_app

    app = compile_medusa_app()
    place_order = app.operations["checkout.place_order"]
    assert place_order.unknown_recovery_directive == "reconcile_unknown_order"

    now = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
    resume_capability = ResumeCapabilityBinding(
        handle="opaque-checkout-review-resume",
        session_id="session-1",
        node_id="checkout.review",
        expires_at=now + timedelta(minutes=5),
    )
    session = session_factory(
        app=app,
        node_id="checkout.review",
        resume_capabilities=(resume_capability,),
    )
    unknown = _failure(
        operation_id=place_order.id,
        recovery_directive=place_order.unknown_recovery_directive,
    )
    session = session.model_copy(
        update={
            "public_state": session.public_state.model_copy(update={"failure": unknown})
        }
    )

    projection = ProjectionProjector(app, now=now).project(session)

    assert projection.surfaces.active.component == "checkout.recovery"
    assert projection.legal_operations == ()
    assert "checkout.place_order" not in projection.legal_operation_ids


def test_medusa_checkout_unknown_outcome_projects_recovery_for_order_binding() -> None:
    from medusa_agent.composition import compile_medusa_app

    app = compile_medusa_app()
    place_order = app.operations["checkout.place_order"]
    now = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
    resume_capability = ResumeCapabilityBinding(
        handle="opaque-checkout-review-resume",
        session_id="session-1",
        node_id="checkout.review",
        expires_at=now + timedelta(minutes=5),
    )
    session = session_factory(
        app=app,
        node_id="checkout.review",
        resume_capabilities=(resume_capability,),
    )
    unknown = _failure(
        operation_id=place_order.id,
        recovery_directive=place_order.unknown_recovery_directive,
    )
    session = session.model_copy(
        update={
            "private_state": session.private_state.model_copy(
                update={
                    "entity_bindings": (
                        PrivateEntityBinding(
                            entity_kind="order",
                            public_handle="order-recovery-ref",
                            private_id="order-private-id",
                            allowed_operation_ids=("orders.reconcile",),
                        ),
                    )
                }
            ),
            "public_state": session.public_state.model_copy(
                update={
                    "entity_handles": (
                        PublicEntityHandle(
                            entity_kind="order",
                            handle="order-recovery-ref",
                        ),
                    ),
                    "failure": unknown,
                }
            ),
        }
    )

    projection = ProjectionProjector(app, now=now).project(session)

    assert projection.legal_operation_ids == ("orders.reconcile",)
    assert tuple(entity.handle for entity in projection.entities) == (
        "order-recovery-ref",
    )
