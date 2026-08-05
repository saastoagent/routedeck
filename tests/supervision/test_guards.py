from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from pydantic import ValidationError

from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import (
    DeliveryPhase,
    OperationOutcome,
    OperationSource,
    Operation,
    SafetyClass,
)


def _failure() -> RouteDeckFailure:
    return RouteDeckFailure(
        kind=FailureKind.GUARD,
        code="item_not_allowed",
        phase="guard",
        correlation_id="correlation-1",
        operation_id="test.write",
        request_id="request-1",
        public_message="That item is not available for this operation.",
    )


@pytest.mark.parametrize(
    ("node_update", "failure_code"),
    (
        ({"context_providers": ()}, "provider_not_declared_at_node"),
        ({"guards": ()}, "guard_not_declared_at_node"),
    ),
)
@pytest.mark.asyncio
async def test_malformed_node_scope_fails_before_runtime_invocation(
    node_update,
    failure_code,
    compiled_app,
    bound_app,
    store,
    runner_factory,
    provider,
    guard,
    executor,
) -> None:
    from routedeck_core.app import BoundApplication
    from routedeck_core.contracts.operations import OperationRequest
    from routedeck_core.state.session import navgraph_version

    malformed_node = compiled_app.graph.nodes[0].model_copy(update=node_update)
    malformed_compiled = replace(
        compiled_app,
        graph=compiled_app.graph.model_copy(update={"nodes": (malformed_node,)}),
        nodes={malformed_node.id: malformed_node},
    )
    malformed_app = BoundApplication(
        app=malformed_compiled,
        bindings=bound_app.bindings,
    )
    session = store.sessions["session-1"]
    store.sessions["session-1"] = session.model_copy(
        update={"navgraph_version": navgraph_version(malformed_compiled)}
    )

    result = await runner_factory(app=malformed_app).run(
        OperationRequest(
            session_id="session-1",
            request_id=f"malformed-{failure_code}",
            expected_session_version=1,
            operation_id="test.write",
            source="surface",
            arguments={"quantity": 2},
        )
    )

    assert result.failure is not None
    assert result.failure.code == failure_code
    assert provider.calls == []
    assert guard.calls == []
    assert executor.calls == []


def test_execution_context_keeps_resolved_private_ids_secret() -> None:
    from routedeck_core.ports.executor import ExecutionContext, ResolvedEntityInput

    context = ExecutionContext(
        session_id="session-1",
        request_id="request-1",
        attempt_id="attempt-1",
        node_id="catalog.product",
        source=OperationSource.SURFACE,
        context_fingerprint="context-1",
        resolved_entities=(
            ResolvedEntityInput(
                argument_name="variant_ref",
                entity_kind="variant",
                private_id="private-variant-sentinel",
            ),
        ),
    )

    assert context.private_entity_id("variant_ref") == "private-variant-sentinel"
    assert "private-variant-sentinel" not in context.model_dump_json()


def test_registered_executor_invokes_only_the_explicit_binding() -> None:
    from routedeck_core.ports.executor import (
        ExecutionContext,
        OperationBinding,
        RegisteredOperationExecutor,
    )

    calls: list[str] = []

    async def handler(arguments, context):
        del arguments
        calls.append(context.request_id)
        return OperationOutcome(
            outcome="advanced",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        )

    operation = Operation(
        id="test.advance",
        title="Advance",
        description="Test operation.",
        safety_class=SafetyClass.WRITE_EXTERNAL,
        allowed_sources=frozenset(OperationSource),
        unknown_recovery_directive="Verify the write before retrying.",
        outcomes=("advanced",),
    )
    binding = OperationBinding(operation=operation, handler=handler)
    context = ExecutionContext(
        session_id="session-1",
        request_id="request-1",
        attempt_id="attempt-1",
        node_id="test.start",
        source=OperationSource.AGENT,
        context_fingerprint="context-1",
    )

    outcome = asyncio.run(RegisteredOperationExecutor().execute(binding, {}, context))

    assert outcome.outcome == "advanced"
    assert calls == ["request-1"]


def test_guard_decision_requires_a_typed_failure_when_denied() -> None:
    from routedeck_core.supervision.guards import GuardDecision

    failure = _failure()

    assert GuardDecision.blocked(failure).failure == failure
    assert GuardDecision.needs_input(failure).disposition.value == "needs_input"
    with pytest.raises(ValidationError, match="denied guard"):
        GuardDecision(allowed=False)


def test_guard_decision_rejects_contradictory_allow_and_denial_contracts() -> None:
    from routedeck_core.contracts.operations import OperationDisposition
    from routedeck_core.supervision.guards import GuardDecision

    failure = _failure()

    with pytest.raises(ValidationError, match="allowed guard decisions"):
        GuardDecision(
            allowed=True,
            disposition=OperationDisposition.BLOCKED,
            failure=failure,
        )
    with pytest.raises(ValidationError, match="blocked or needs_input"):
        GuardDecision(
            allowed=False,
            disposition=OperationDisposition.FAILED,
            failure=failure,
        )


@pytest.mark.asyncio
async def test_provider_output_is_validated_before_guard_or_executor(
    runner,
    provider,
    guard,
    executor,
) -> None:
    from routedeck_core.contracts.operations import OperationRequest

    provider.values = {"revision": "malformed"}
    result = await runner.run(
        OperationRequest(
            session_id="session-1",
            request_id="provider-invalid",
            expected_session_version=1,
            operation_id="test.write",
            source="surface",
            arguments={"quantity": 2},
        )
    )

    assert result.failure.code == "invalid_context_provider_result"
    assert guard.calls == []
    assert executor.calls == []


@pytest.mark.asyncio
async def test_stale_session_and_disabled_operation_fail_before_authority_refresh(
    runner,
    store,
    provider,
    guard,
    executor,
) -> None:
    from routedeck_core.contracts.operations import OperationRequest

    stale = await runner.run(
        OperationRequest(
            session_id="session-1",
            request_id="stale-version",
            expected_session_version=0,
            operation_id="test.write",
            source="surface",
            arguments={"quantity": 2},
        )
    )
    session = store.sessions["session-1"]
    store.sessions["session-1"] = session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={"disabled_operation_ids": ("test.write",)}
            )
        }
    )
    disabled = await runner.run(
        OperationRequest(
            session_id="session-1",
            request_id="disabled-operation",
            expected_session_version=1,
            operation_id="test.write",
            source="surface",
            arguments={"quantity": 2},
        )
    )

    assert stale.failure.code == "version_conflict"
    assert disabled.failure.code == "operation_not_available"
    assert provider.calls == []
    assert guard.calls == []
    assert executor.calls == []


@pytest.mark.asyncio
async def test_incompatible_session_schema_fails_before_authority_refresh(
    runner,
    store,
    provider,
    guard,
    executor,
) -> None:
    from routedeck_core.contracts.operations import OperationRequest

    session = store.sessions["session-1"]
    store.sessions["session-1"] = session.model_copy(
        update={"schema_version": session.schema_version + 1}
    )

    result = await runner.run(
        OperationRequest(
            session_id="session-1",
            request_id="incompatible-session",
            expected_session_version=1,
            operation_id="test.write",
            source="surface",
            arguments={"quantity": 2},
        )
    )

    assert result.failure.code == "session_upgrade_required"
    assert provider.calls == []
    assert guard.calls == []
    assert executor.calls == []


@pytest.mark.asyncio
async def test_invalid_entity_handle_shape_fails_before_guard_or_executor(
    runner,
    store,
    provider,
    guard,
    executor,
) -> None:
    from routedeck_core.contracts.operations import OperationRequest
    from routedeck_core.contracts.projection import FrozenJsonObject

    request = OperationRequest(
        session_id="session-1",
        request_id="invalid-entity-shape",
        expected_session_version=1,
        operation_id="test.bound_write",
        source="surface",
        arguments={"item_ref": "item-public-1"},
    )
    malformed = request.model_copy(
        update={"arguments": FrozenJsonObject({"item_ref": 7})}
    )

    resolved = runner._resolve_entities(
        session=store.sessions["session-1"],
        request=malformed,
        operation=runner.app.app.operations["test.bound_write"],
    )

    assert resolved is None
    assert provider.calls == []
    assert guard.calls == []
    assert executor.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("missing_binding", "failure_code"),
    (
        ("provider", "missing_provider_binding"),
        ("guard", "missing_guard_binding"),
    ),
)
async def test_declared_authority_without_runtime_binding_fails_closed(
    missing_binding,
    failure_code,
    bound_app,
    runner_factory,
    provider,
    guard,
    executor,
) -> None:
    from routedeck_core.app import BoundApplication
    from routedeck_core.contracts.operations import OperationRequest

    bindings = replace(
        bound_app.bindings,
        providers={} if missing_binding == "provider" else bound_app.bindings.providers,
        guards={} if missing_binding == "guard" else bound_app.bindings.guards,
    )
    malformed = BoundApplication(app=bound_app.app, bindings=bindings)

    result = await runner_factory(app=malformed).run(
        OperationRequest(
            session_id="session-1",
            request_id=f"missing-{missing_binding}",
            expected_session_version=1,
            operation_id="test.write",
            source="surface",
            arguments={"quantity": 2},
        )
    )

    assert result.failure.code == failure_code
    assert executor.calls == []
    if missing_binding == "provider":
        assert provider.calls == []
        assert guard.calls == []
    else:
        assert provider.calls == ["missing-guard"]
        assert guard.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("authority", "failure_code"),
    (
        ("provider", "invalid_context_provider_result"),
        ("guard", "invalid_guard_result"),
    ),
)
async def test_untyped_authority_result_fails_closed_before_execution(
    authority,
    failure_code,
    bound_app,
    runner_factory,
    executor,
) -> None:
    from routedeck_core.app import BoundApplication
    from routedeck_core.contracts.operations import OperationRequest

    async def untyped_result(_context):
        return {"allowed": True}

    bindings = replace(
        bound_app.bindings,
        providers=(
            {ref: untyped_result for ref in bound_app.bindings.providers}
            if authority == "provider"
            else bound_app.bindings.providers
        ),
        guards=(
            {ref: untyped_result for ref in bound_app.bindings.guards}
            if authority == "guard"
            else bound_app.bindings.guards
        ),
    )
    malformed = BoundApplication(app=bound_app.app, bindings=bindings)

    result = await runner_factory(app=malformed).run(
        OperationRequest(
            session_id="session-1",
            request_id=f"untyped-{authority}",
            expected_session_version=1,
            operation_id="test.write",
            source="surface",
            arguments={"quantity": 2},
        )
    )

    assert result.failure.code == failure_code
    assert executor.calls == []
