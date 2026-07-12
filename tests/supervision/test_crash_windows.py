from __future__ import annotations

import pytest

from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationPhase,
    OperationRequest,
    OperationSource,
)


def write_request(
    *,
    request_id: str = "write-1",
    expected_session_version: int = 1,
) -> OperationRequest:
    return OperationRequest(
        session_id="session-1",
        request_id=request_id,
        expected_session_version=expected_session_version,
        operation_id="test.write",
        source=OperationSource.SURFACE,
        arguments={"quantity": 2},
    )


@pytest.mark.asyncio
async def test_claim_without_send_boundary_is_not_sent_and_never_auto_reexecutes(
    runner,
    store,
    executor,
) -> None:
    store.fail_record_started_once = True

    first = await runner.run(write_request())
    recovered = await runner.run(write_request(expected_session_version=0))

    assert first.disposition is OperationDisposition.FAILED
    assert first.failure.kind.value == "persistence"
    assert first.evidence.delivery_phase.value == "not_sent"
    assert recovered.disposition is OperationDisposition.FAILED
    assert executor.calls == []
    stored = await store.find_attempt("session-1", "write-1")
    assert OperationPhase.TOOL_STARTED not in stored.evidence.phases


@pytest.mark.asyncio
async def test_started_without_journal_recovers_unknown_without_second_call(
    runner,
    store,
    handlers,
    executor,
) -> None:
    handlers["test.write"].raises = RuntimeError("private exception sentinel")
    store.fail_mark_unknown_once = True

    with pytest.raises(OSError, match="unknown-state commit"):
        await runner.run(write_request())
    handlers["test.write"].raises = None
    recovered = await runner.run(write_request(expected_session_version=0))

    assert recovered.disposition is OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
    assert recovered.evidence.delivery_phase.value == "possibly_sent"
    assert executor.call_count("test.write") == 1
    snapshot = await store.load("session-1")
    assert "test.write" in snapshot.state.public_state.disabled_operation_ids


@pytest.mark.asyncio
async def test_journaled_result_reapplies_after_commit_failure_without_reexecution(
    runner,
    store,
    executor,
) -> None:
    store.fail_commit_attempt_once = True

    first = await runner.run(write_request())
    recovered = await runner.run(write_request(expected_session_version=0))

    assert first.disposition is OperationDisposition.FAILED
    assert first.failure.code == "state_commit_failed"
    assert recovered.disposition is OperationDisposition.COMPLETED
    assert recovered.outcome == "written"
    assert executor.call_count("test.write") == 1


@pytest.mark.asyncio
async def test_response_received_but_journal_failure_is_unknown_and_not_retried(
    runner,
    store,
    executor,
) -> None:
    store.fail_record_result = True

    unknown = await runner.run(write_request())
    replay = await runner.run(write_request(expected_session_version=0))

    assert unknown.disposition is OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
    assert unknown.evidence.delivery_phase.value == "response_received"
    assert replay == unknown
    assert executor.call_count("test.write") == 1
