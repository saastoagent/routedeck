from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import ValidationError

from medusa_agent.composition import compile_medusa_app
from medusa_agent.session import BuyerMarket, create_medusa_session
from routedeck_core.app import CompiledApplication
from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationToolCall,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import OperationSource
from routedeck_core.contracts.projection import FrozenJsonObject, PublicEntityHandle
from routedeck_core.contracts.session import (
    OperationAttempt,
    OperationState,
    PendingReview,
    PrivateEntityBinding,
    ReviewResolution,
)
from routedeck_testing.factories import session_factory
from routedeck_langgraph.model_context import (
    build_model_context,
    merge_reconstructed_messages,
    reconstruct_messages,
)


def test_tool_turn_requires_typed_call_metadata() -> None:
    with pytest.raises(ValidationError, match="typed tool-call metadata"):
        FinalizedConversationTurn(
            turn_id="previous-tool-turn",
            role=ConversationRole.TOOL,
            content="previous observation",
            request_id="chat-previous",
        )


def test_reconstruct_messages_pairs_each_typed_tool_observation_with_its_call() -> None:
    conversation = (
        FinalizedConversationTurn(
            turn_id="turn-user",
            role=ConversationRole.USER,
            content="Add two shirts.",
            request_id="chat-1",
        ),
        FinalizedConversationTurn(
            turn_id="turn-tool",
            role=ConversationRole.TOOL,
            content='{"disposition":"completed"}',
            request_id="chat-1",
            tool_call=ConversationToolCall(
                call_id="call-cart-add",
                name="cart.add_item",
                arguments=FrozenJsonObject(
                    {"variant_handle": "variant-public", "quantity": 2}
                ),
                assistant_content="I will add those now.",
            ),
            tool_status="success",
        ),
        FinalizedConversationTurn(
            turn_id="turn-assistant",
            role=ConversationRole.ASSISTANT,
            content="Two shirts are in your cart.",
            request_id="chat-1",
        ),
    )

    messages = reconstruct_messages(SimpleNamespace(conversation=conversation))

    assert [type(message) for message in messages] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
    ]
    call_envelope = messages[1]
    assert isinstance(call_envelope, AIMessage)
    assert call_envelope.text == "I will add those now."
    assert call_envelope.tool_calls == [
        {
            "name": "cart.add_item",
            "args": {"variant_handle": "variant-public", "quantity": 2},
            "id": "call-cart-add",
            "type": "tool_call",
        }
    ]
    observation = messages[2]
    assert isinstance(observation, ToolMessage)
    assert observation.tool_call_id == "call-cart-add"
    assert observation.name == "cart.add_item"
    assert observation.status == "success"


def test_merge_reconstructed_messages_preserves_repeated_current_user_turn() -> None:
    durable = HumanMessage(content="Show me the cart.", id="turn-old")
    current = HumanMessage(content="Show me the cart.", id="turn-current")

    merged = merge_reconstructed_messages((durable,), (current,))

    assert [message.id for message in merged] == ["turn-old", "turn-current"]


def test_merge_reconstructed_messages_prefers_current_message_for_same_id() -> None:
    durable = HumanMessage(content="durable", id="turn-shared")
    current = HumanMessage(content="current", id="turn-shared")

    merged = merge_reconstructed_messages((durable,), (current,))

    assert merged == [current]


@pytest.mark.parametrize(
    ("resolution", "expected"),
    [
        (ReviewResolution.PENDING, True),
        (ReviewResolution.ACCEPTED, False),
        (ReviewResolution.REJECTED, False),
        (ReviewResolution.STALE, False),
        (ReviewResolution.EXPIRED, False),
    ],
)
def test_model_context_reports_review_pending_only_for_pending_resolution(
    resolution: ReviewResolution,
    expected: bool,
) -> None:
    session = create_medusa_session(
        app=compile_medusa_app(),
        session_id="session-review-status",
        market=BuyerMarket(
            region_handle="region-public",
            country_code="us",
            currency_code="usd",
            sales_channel_handle="channel-public",
        ),
    )
    attempt = OperationAttempt(
        attempt_id="attempt-review-status",
        request_id="request-review-status",
        request_fingerprint="request-fingerprint",
        operation_id="checkout.place_order",
        source=OperationSource.AGENT,
        expected_session_version=session.session_version,
        context_fingerprint="context-fingerprint",
    )
    review = PendingReview(
        review_id="review-status",
        attempt=attempt,
        operation_spec_version="operation-spec-version",
        proposal_fingerprint="proposal-fingerprint",
        projection_version=session.projection_version,
        authoritative_context_fingerprint="context-fingerprint",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        resolution=resolution,
    )
    session = session.model_copy(
        update={
            "operation": OperationState(
                active_attempt=attempt,
                pending_review=review,
            )
        }
    )

    context = build_model_context(session, compile_medusa_app())

    assert context.status.review_pending is expected


def test_unknown_order_context_hides_reconcile_without_authorized_order() -> None:
    app = compile_medusa_app()
    session = _unknown_order_session(app)

    context = build_model_context(session, app)

    assert context.active_surface.component == "checkout.recovery"
    assert context.legal_tools == ()


def test_unknown_order_context_exposes_reconcile_for_authorized_order() -> None:
    app = compile_medusa_app()
    session = _unknown_order_session(app)
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
                    )
                }
            ),
        }
    )

    context = build_model_context(session, app)

    assert context.active_surface.component == "checkout.recovery"
    assert tuple(tool.name for tool in context.legal_tools) == ("orders.reconcile",)
    assert tuple(entity.handle for entity in context.visible_entities) == (
        "order-recovery-ref",
    )


def _unknown_order_session(app: CompiledApplication):
    session = session_factory(app=app, node_id="checkout.review")
    failure = RouteDeckFailure(
        kind=FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
        code="external_outcome_unknown",
        phase="order_completion",
        correlation_id="correlation-1",
        operation_id="checkout.place_order",
        request_id="request-1",
        public_message="The order outcome is uncertain.",
        recovery_directive="reconcile_unknown_order",
    )
    return session.model_copy(
        update={
            "public_state": session.public_state.model_copy(
                update={
                    "failure": failure,
                    "disabled_operation_ids": ("checkout.place_order",),
                }
            )
        }
    )
