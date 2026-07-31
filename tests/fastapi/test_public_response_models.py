from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError

from routedeck_core.contracts.conversation import (
    ConversationRunKind,
    ConversationRunSnapshot,
    ConversationRunStage,
)
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationEvidence,
    OperationPhase,
    OperationResult,
    OperationSource,
)
from routedeck_fastapi.conversation_runs import (
    ConversationRunEnvelope,
    public_conversation_run_envelope,
)
from routedeck_fastapi.conversation_projection import PublicConversationTurn
from routedeck_fastapi.conversation_sse import (
    ConversationAssistantDeltaPayload,
    ConversationAssistantEndPayload,
    ConversationAssistantResetPayload,
    ConversationChatErrorPayload,
    ConversationReviewRequiredPayload,
    ConversationSnapshotPayload,
    ConversationStreamEndPayload,
    ConversationStreamStartPayload,
    ConversationUserMessagePayload,
    encode_conversation_sse,
)
from routedeck_fastapi.responses import (
    PublicOperationResult,
    operation_response,
)
from routedeck_fastapi.sse import StreamResetPayload, encode_stream_reset


def test_operation_response_uses_public_pydantic_model() -> None:
    result = OperationResult(
        disposition=OperationDisposition.COMPLETED,
        session_id="private-session-id",
        request_id="request-1",
        operation_id="catalog.list",
        session_version=2,
        projection_version=2,
        evidence=OperationEvidence(
            source=OperationSource.SURFACE,
            phases=(OperationPhase.RECEIVED, OperationPhase.COMPLETED),
            attempt_id="attempt-1",
            request_fingerprint="fingerprint-1",
        ),
        outcome="listed",
    )

    response = operation_response(result)
    payload = json.loads(response.body)

    assert payload == PublicOperationResult.from_result(result).model_dump(mode="json")
    assert set(payload) == set(PublicOperationResult.model_fields)
    assert "session_id" not in payload


def test_conversation_run_envelope_uses_public_pydantic_model() -> None:
    snapshot = ConversationRunSnapshot(
        request_id="request-1",
        kind=ConversationRunKind.ASSISTANT_INITIATED,
        stage=ConversationRunStage.STARTING,
        cursor=1,
    )

    payload = public_conversation_run_envelope(snapshot)

    assert payload == ConversationRunEnvelope.from_snapshot(snapshot).model_dump(
        mode="json"
    )


def test_stream_reset_encoder_uses_public_pydantic_model() -> None:
    encoded = encode_stream_reset(requested_after=3, retained_from_cursor=5)
    data = encoded.decode("utf-8").split("data: ", maxsplit=1)[1].strip()

    payload = json.loads(data)

    assert payload == StreamResetPayload(
        requested_after=3,
        retained_from_cursor=5,
    ).model_dump(mode="json")


@pytest.mark.parametrize(
    ("event", "model", "payload"),
    [
        (
            "stream_start",
            ConversationStreamStartPayload,
            {"request_id": "request-1", "session_version": 0},
        ),
        (
            "conversation_snapshot",
            ConversationSnapshotPayload,
            {
                "turns": [
                    {
                        "turn_id": "turn-1",
                        "request_id": None,
                        "role": "assistant",
                        "content": "",
                    }
                ]
            },
        ),
        (
            "user_message",
            ConversationUserMessagePayload,
            {
                "content": "Hello",
                "request_id": "request-1",
                "turn_id": "turn-1",
            },
        ),
        (
            "assistant_delta",
            ConversationAssistantDeltaPayload,
            {"content": "Hello", "request_id": "request-1"},
        ),
        (
            "assistant_reset",
            ConversationAssistantResetPayload,
            {"request_id": "request-1"},
        ),
        (
            "assistant_end",
            ConversationAssistantEndPayload,
            {
                "request_id": "request-1",
                "session_version": 2,
                "projection_version": 3,
                "turn_id": "turn-1",
            },
        ),
        (
            "review_required",
            ConversationReviewRequiredPayload,
            {
                "status": "requires_review",
                "operation_id": "operation-1",
                "review_id": "review-1",
                "expires_at": "2026-07-31T12:00:00+00:00",
            },
        ),
        (
            "chat_error",
            ConversationChatErrorPayload,
            {"code": "turn_interrupted", "message": "Interrupted."},
        ),
        (
            "stream_end",
            ConversationStreamEndPayload,
            {"request_id": "request-1", "status": "completed"},
        ),
    ],
)
def test_legacy_conversation_sse_encoder_uses_public_pydantic_models(
    event: str,
    model: type[BaseModel],
    payload: dict[str, object],
) -> None:
    encoded = encode_conversation_sse(event, payload)
    data = encoded.split("data: ", maxsplit=1)[1].strip()

    assert json.loads(data) == model.model_validate(payload).model_dump(mode="json")


@pytest.mark.parametrize(
    ("event", "payload"),
    [
        ("stream_start", {"request_id": "request-1", "session_version": 0}),
        ("conversation_snapshot", {"turns": []}),
        (
            "user_message",
            {"content": "Hello", "request_id": "request-1", "turn_id": "turn-1"},
        ),
        (
            "assistant_delta",
            {"content": "Hello", "request_id": "request-1"},
        ),
        ("assistant_reset", {"request_id": "request-1"}),
        (
            "assistant_end",
            {
                "request_id": "request-1",
                "session_version": 2,
                "projection_version": 3,
                "turn_id": "turn-1",
            },
        ),
        (
            "review_required",
            {
                "status": "requires_review",
                "operation_id": "operation-1",
                "review_id": "review-1",
                "expires_at": "2026-07-31T12:00:00+00:00",
            },
        ),
        (
            "chat_error",
            {"code": "turn_interrupted", "message": "Interrupted."},
        ),
        ("stream_end", {"request_id": "request-1", "status": "completed"}),
    ],
)
def test_legacy_conversation_sse_encoder_rejects_unknown_fields(
    event: str,
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        encode_conversation_sse(event, {**payload, "undeclared": True})


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            ConversationStreamStartPayload,
            {"request_id": "x" * 257, "session_version": 0},
        ),
        (
            ConversationUserMessagePayload,
            {"content": "Hello", "request_id": "x" * 257, "turn_id": "turn-1"},
        ),
        (
            ConversationAssistantDeltaPayload,
            {"content": "Hello", "request_id": "x" * 257},
        ),
        (ConversationAssistantResetPayload, {"request_id": "x" * 257}),
        (
            ConversationAssistantEndPayload,
            {
                "request_id": "x" * 257,
                "session_version": 0,
                "projection_version": 0,
                "turn_id": "turn-1",
            },
        ),
        (
            ConversationStreamEndPayload,
            {"request_id": "x" * 257, "status": "completed"},
        ),
    ],
)
def test_legacy_conversation_sse_models_reject_overlong_request_ids(
    model: type[BaseModel],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_legacy_conversation_sse_models_accept_exact_transport_boundaries() -> None:
    maximum = 9_007_199_254_740_991

    start = ConversationStreamStartPayload(
        request_id="x" * 256,
        session_version=maximum,
    )
    completed = ConversationAssistantEndPayload(
        request_id="x" * 256,
        session_version=maximum,
        projection_version=maximum,
        turn_id="turn-1",
    )

    assert start.session_version == maximum
    assert completed.projection_version == maximum


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            ConversationStreamStartPayload,
            {"request_id": "request-1", "session_version": 9_007_199_254_740_992},
        ),
        (
            ConversationAssistantEndPayload,
            {
                "request_id": "request-1",
                "session_version": 9_007_199_254_740_992,
                "projection_version": 0,
                "turn_id": "turn-1",
            },
        ),
        (
            ConversationAssistantEndPayload,
            {
                "request_id": "request-1",
                "session_version": 0,
                "projection_version": 9_007_199_254_740_992,
                "turn_id": "turn-1",
            },
        ),
    ],
)
def test_legacy_conversation_sse_models_reject_unsafe_versions(
    model: type[BaseModel],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_public_history_turn_empty_strings_match_canonical_turn_guarantees() -> None:
    with pytest.raises(ValidationError):
        PublicConversationTurn(
            turn_id="",
            request_id=None,
            role="assistant",
            content="",
        )

    turn = PublicConversationTurn(
        turn_id="turn-1",
        request_id="",
        role="assistant",
        content="",
    )

    assert turn.request_id == ""
