from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGenerationChunk
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session as OrmSession

from main import create_medusa_app
from medusa_agent.agent import create_medusa_agent, create_medusa_entry_agent
from medusa_agent.bindings import bind_medusa_app
from medusa_agent.composition import compile_medusa_app
from medusa_agent.features.catalog.providers import CatalogRouteKeyValidator
from medusa_agent.features.checkout.providers import EncryptedCheckoutPrivateFormReader
from medusa_agent.medusa.client.models import (
    CalculatedPrice,
    Cart,
    CartLineItem,
    CartResult,
    CartShippingMethod,
    CreateCartRequest,
    CreateCartResult,
    MedusaCart,
    PaymentCollection,
    PaymentSession,
    Product,
    ProductPage,
    ProductPageResult,
    ProductQuery,
    ProductVariant,
    StoreAddress,
)
from medusa_agent.session import BuyerMarket, create_medusa_session
from routedeck_core.app import ContextProviderHandler, GuardHandler, OperationHandler
from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
)
from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.operations import (
    GuardRef,
    OperationOutcome,
    OperationRef,
    ProviderRef,
)
from routedeck_core.contracts.projection import PublicEntityHandle
from routedeck_core.contracts.session import (
    Location,
    PrivateDraft,
    PrivateEntityBinding,
)
from routedeck_core.ports.executor import ExecutionContext
from routedeck_core.supervision.guards import (
    GuardDecision,
    GuardInvocationContext,
    ProviderInvocationContext,
    ProviderResult,
)
from routedeck_fastapi.sse import encode_event
from routedeck_langgraph import (
    RouteDeckLangGraphDriverFactory,
    RouteDeckLangGraphGraphs,
    operation_tool_name,
)
from routedeck_sqlalchemy import (
    SqlAlchemyRuntimeResources,
    open_sqlalchemy_routedeck_runtime,
)
from routedeck_sqlalchemy.models import TurnLeaseRow
from routedeck_testing import ScriptedTextModel, ScriptedToolModel, tool_call


_OWNED_OPERATION_IDS = {
    "cart.create",
    "cart.add_item",
    "cart.open",
    "cart.update_item",
    "cart.remove_item",
    "catalog.list",
    "catalog.search",
    "catalog.open_product",
    "catalog.open_product_by_route",
    "catalog.select_variant",
    "catalog.continue_shopping",
    "checkout.start",
    "checkout.save_contact",
    "checkout.select_shipping",
    "checkout.select_payment",
    "checkout.place_order",
    "orders.reconcile",
    "checkout.select_payment",
    "checkout.place_order",
    "orders.reconcile",
}
_OWNED_PROVIDER_IDS = {
    "cart.buyer_market",
    "cart.current",
    "cart.binding",
    "cart.items",
    "catalog.products",
    "catalog.product",
    "catalog.variants",
    "checkout.facts",
    "checkout.shipping_options",
    "checkout.payment_providers",
    "orders.confirmed_order",
    "checkout.payment_providers",
    "orders.confirmed_order",
}
_OWNED_GUARD_IDS = {
    "cart.absent",
    "cart.exists",
    "catalog.public_product",
    "catalog.variant_allowed",
    "checkout.cart_ready",
    "checkout.contact_valid",
    "checkout.shipping_valid",
    "checkout.payment_valid",
    "checkout.review_current",
    "checkout.payment_valid",
    "checkout.review_current",
}
_PAYMENT_PROVIDER_ID = "pp_system_default"


@dataclass
class _ScriptedStoreFixture:
    """Exact test-only Store fixture for the chat flow's selected calls."""

    calls: list[str] = field(default_factory=list)
    private_cart_id: str = "private-cart-chat-smoke"
    review_ready: bool = False

    async def create_cart(self, request: CreateCartRequest) -> CreateCartResult:
        assert request.region_id == "private-region-chat-smoke"
        assert request.country_code == "us"
        assert request.sales_channel_id == "private-channel-chat-smoke"
        self.calls.append("create_cart")
        return CreateCartResult.succeeded(
            MedusaCart(
                id=SecretStr(self.private_cart_id),
                currency_code="usd",
            )
        )

    async def list_products(self, query: ProductQuery) -> ProductPageResult:
        assert query.region_id == "private-region-chat-smoke"
        assert query.query is None
        self.calls.append("list_products")
        return ProductPageResult.succeeded(
            ProductPage(
                products=(
                    Product(
                        id=SecretStr("private-product-chat-smoke"),
                        handle="linen-shirt",
                        title="Linen shirt",
                        variants=(
                            ProductVariant(
                                id=SecretStr("private-variant-chat-smoke"),
                                title="Default",
                                inventory_quantity=4,
                                calculated_price=CalculatedPrice(
                                    calculated_amount=4900,
                                    currency_code="usd",
                                ),
                            ),
                        ),
                    ),
                ),
                count=1,
                offset=0,
                limit=20,
            )
        )

    async def get_cart(self, cart_id: str) -> CartResult:
        assert cart_id == self.private_cart_id
        self.calls.append("get_cart")
        if self.review_ready:
            address = StoreAddress(
                first_name="Route",
                last_name="Deck",
                address_1="1 Durable Way",
                postal_code="10001",
                city="New York",
                country_code="us",
            )
            return CartResult.succeeded(
                Cart(
                    id=SecretStr(self.private_cart_id),
                    currency_code="usd",
                    region_id=SecretStr("private-region-chat-smoke"),
                    sales_channel_id=SecretStr("private-channel-chat-smoke"),
                    email="buyer@example.test",
                    subtotal=5400,
                    item_subtotal=4900,
                    shipping_total=500,
                    total=5400,
                    items=(
                        CartLineItem(
                            id=SecretStr("private-line-chat-smoke"),
                            variant_id=SecretStr("private-variant-chat-smoke"),
                            title="Linen shirt",
                            quantity=1,
                            unit_price=4900,
                            total=4900,
                        ),
                    ),
                    shipping_methods=(
                        CartShippingMethod(
                            shipping_option_id=SecretStr("private-shipping-chat-smoke"),
                            name="Standard",
                            amount=500,
                        ),
                    ),
                    shipping_address=address,
                    billing_address=address,
                    payment_collection=PaymentCollection(
                        id=SecretStr("private-payment-collection-chat-smoke"),
                        currency_code="usd",
                        amount=5400,
                        payment_sessions=(
                            PaymentSession(
                                id=SecretStr("private-payment-session-chat-smoke"),
                                provider_id=_PAYMENT_PROVIDER_ID,
                                status="pending",
                            ),
                        ),
                    ),
                )
            )
        return CartResult.succeeded(
            Cart(
                id=SecretStr(self.private_cart_id),
                currency_code="usd",
                region_id=SecretStr("private-region-chat-smoke"),
                sales_channel_id=SecretStr("private-channel-chat-smoke"),
                item_subtotal=0,
                items=(),
            )
        )


class _UnexpectedHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        del arguments, context
        raise AssertionError("an unrelated operation ran in the chat smoke")


class _UnexpectedProvider:
    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        del context
        raise AssertionError("an unrelated provider ran in the chat smoke")


class _UnexpectedGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        del context
        raise AssertionError("an unrelated guard ran in the chat smoke")


@dataclass(frozen=True)
class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class _Notifier:
    events: list[RouteDeckEvent] = field(default_factory=list)

    async def notify(
        self,
        _session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        self.events.extend(events)

    async def wait_for_events(
        self,
        session_id: str,
        after_cursor: int,
        timeout: timedelta,
    ) -> bool:
        del timeout
        return any(
            event.session_id == session_id and event.cursor > after_cursor
            for event in self.events
        )


class _StreamingScriptedToolModel(ScriptedToolModel):
    async def _astream(
        self,
        messages,
        stop=None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        del stop, run_manager, kwargs
        message = self._result(messages).generations[0].message
        assert isinstance(message, AIMessage)
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content=message.content,
                tool_call_chunks=[
                    {
                        "name": call["name"],
                        "args": json.dumps(call["args"]),
                        "id": call["id"],
                        "index": index,
                        "type": "tool_call_chunk",
                    }
                    for index, call in enumerate(message.tool_calls)
                ],
            )
        )


@pytest.mark.asyncio
async def test_scripted_agent_chat_runs_serial_tools_then_model_only_follow_up(
    tmp_path: Path,
) -> None:
    """Prove the product chat stream on SQLite without a live model or Store."""

    compiled = compile_medusa_app()
    handlers: dict[OperationRef, OperationHandler] = {
        operation.ref: _UnexpectedHandler()
        for operation in compiled.operations.values()
        if operation.id not in _OWNED_OPERATION_IDS
    }
    providers: dict[ProviderRef, ContextProviderHandler] = {
        provider.ref: _UnexpectedProvider()
        for provider in compiled.providers.values()
        if provider.id not in _OWNED_PROVIDER_IDS
    }
    guards: dict[GuardRef, GuardHandler] = {
        guard.ref: _UnexpectedGuard()
        for guard in compiled.guards.values()
        if guard.id not in _OWNED_GUARD_IDS
    }
    market = BuyerMarket(
        region_handle="private-region-chat-smoke",
        country_code="us",
        currency_code="usd",
        sales_channel_handle="private-channel-chat-smoke",
    )
    encryption_key = Fernet.generate_key()
    notifier = _Notifier()
    fixture = _ScriptedStoreFixture()
    ids = count(1)
    database_path = tmp_path / "agent-chat.sqlite"
    database_url = os.environ.get(
        "ROUTEDECK_TEST_DATABASE_URL",
        f"sqlite+pysqlite:///{database_path.as_posix()}",
    )
    model = _StreamingScriptedToolModel(
        [
            tool_call(
                operation_tool_name("cart.create"),
                {},
                call_id="cart-create-agent",
            ).model_copy(update={"content": "I will prepare your cart."}),
            tool_call(
                operation_tool_name("catalog.list"),
                {},
                call_id="catalog-list-agent",
            ),
            tool_call(
                operation_tool_name("cart.open"),
                {},
                call_id="cart-open-agent",
            ),
            AIMessage(content="Your cart is open."),
            AIMessage(content="Your cart is still empty."),
            tool_call(
                operation_tool_name("checkout.place_order"),
                {},
                call_id="place-order-review-agent",
            ),
        ]
    )

    def application_factory(resources: SqlAlchemyRuntimeResources):
        return bind_medusa_app(
            app=compiled,
            client=fixture,  # type: ignore[arg-type]
            private_forms=EncryptedCheckoutPrivateFormReader(
                resources.store,
                resources.codec,
            ),
            configured_payment_provider_id=_PAYMENT_PROVIDER_ID,
            buyer_country_code=market.country_code,
            handlers=handlers,
            providers=providers,
            guards=guards,
        )

    def graph_factory(services):
        return RouteDeckLangGraphGraphs(
            user_message=create_medusa_agent(
                model=model,
                runtime=services,
            ),
            assistant_initiated=create_medusa_entry_agent(
                model=ScriptedTextModel("Hi from the explicit entry test graph.")
            ),
            ignored_event_tags=frozenset(),
        )

    async def keep_created_session(_services, snapshot):
        return snapshot

    runtime = await open_sqlalchemy_routedeck_runtime(
        compiled_app=compiled,
        application_factory=application_factory,
        session_factory=lambda app, session_id: create_medusa_session(
            app=app,
            session_id=session_id,
            market=market,
        ),
        session_initializer=keep_created_session,
        public_key_validator_factory=CatalogRouteKeyValidator.from_session,
        agent_driver_factory=RouteDeckLangGraphDriverFactory(
            graph_factory=graph_factory
        ),
        database_url=database_url,
        encryption_key=encryption_key,
        instance_id="agent-chat-smoke",
        clock=_SystemClock(),
        notifier=notifier,
        id_factory=lambda kind: f"{kind}-{next(ids)}",
        review_ttl=timedelta(minutes=10),
        resume_capability_ttl=timedelta(hours=24),
        default_session_id="agent-chat-default",
    )
    application = create_medusa_app(runtime=runtime)

    try:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://medusa.test",
        ) as client:
            created = await client.post(
                "/api/routedeck/sessions",
                json={"request_id": "create-agent-chat-session"},
            )
            assert created.status_code == 201
            created_projection = created.json()["projection"]
            assert created_projection["graph_node"] == "buyer.home"
            session_id = client.cookies["routedeck_guest"]

            first = await client.post(
                "/api/routedeck/chat",
                json={
                    "request_id": "chat-1",
                    "expected_session_version": created_projection["session_version"],
                    "message": "Show me the catalog and open my cart.",
                },
            )
            assert first.status_code == 200
            assert first.headers["cache-control"] == ("private, no-store, no-transform")
            first_events = _sse_events(first.text)
            assert [event["event"] for event in first_events] == [
                "stream_start",
                "conversation_snapshot",
                "user_message",
                "assistant_delta",
                "assistant_end",
                "stream_end",
            ]
            assert _event(first_events, "assistant_delta")["content"] == (
                "Your cart is open."
            )
            assert "I will prepare your cart." not in first.text
            assert _event(first_events, "stream_end")["status"] == "completed"
            assert fixture.calls == ["create_cart", "list_products", "get_cart"]

            after_tools = await runtime.services.store.load(session_id)
            assert after_tools.state.current.node_id == "cart.summary"
            assert [turn.role.value for turn in after_tools.state.conversation] == [
                "user",
                "tool",
                "tool",
                "tool",
                "assistant",
            ]
            assert all(
                turn.status is ConversationTurnStatus.FINALIZED
                for turn in after_tools.state.conversation
            )
            persisted_tools = tuple(
                turn
                for turn in after_tools.state.conversation
                if turn.role is ConversationRole.TOOL
            )
            assert [turn.tool_call.call_id for turn in persisted_tools] == [
                "cart-create-agent",
                "catalog-list-agent",
                "cart-open-agent",
            ]
            assert [turn.tool_call.name for turn in persisted_tools] == [
                "cart.create",
                "catalog.list",
                "cart.open",
            ]
            assert persisted_tools[0].tool_call.assistant_content == (
                "I will prepare your cart."
            )
            assert all(turn.tool_status == "success" for turn in persisted_tools)
            model_calls_before_history = len(model.calls)
            public_history = await client.get("/api/routedeck/conversation")
            assert public_history.status_code == 200
            assert public_history.headers["cache-control"] == "private, no-store"
            assert public_history.json() == {
                "turns": [
                    {
                        "turn_id": after_tools.state.conversation[0].turn_id,
                        "request_id": "chat-1",
                        "role": "user",
                        "content": "Show me the catalog and open my cart.",
                    },
                    {
                        "turn_id": after_tools.state.conversation[-1].turn_id,
                        "request_id": "chat-1",
                        "role": "assistant",
                        "content": "Your cart is open.",
                    },
                ]
            }
            assert len(model.calls) == model_calls_before_history
            assert fixture.calls == ["create_cart", "list_products", "get_cart"]
            current_user_messages = [
                message
                for message in model.calls[0].messages
                if isinstance(message, HumanMessage)
                and message.content == "Show me the catalog and open my cart."
            ]
            assert [message.id for message in current_user_messages] == [
                after_tools.state.conversation[0].turn_id
            ]
            assert fixture.private_cart_id not in (
                after_tools.state.public_state.model_dump_json()
            )
            assert fixture.private_cart_id not in json.dumps(
                [
                    turn.model_dump(mode="json")
                    for turn in after_tools.state.conversation
                ]
            )
            assert fixture.private_cart_id not in first.text
            public_event_frames = b"".join(
                encode_event(event) for event in notifier.events
            ).decode("utf-8")
            assert session_id not in public_event_frames
            child_attempts = [
                await runtime.services.store.find_attempt(
                    session_id,
                    f"chat-1:{call_id}",
                )
                for call_id in (
                    "cart-create-agent",
                    "catalog-list-agent",
                    "cart-open-agent",
                )
            ]
            assert all(attempt is not None for attempt in child_attempts)
            assert all(
                attempt.attempt.parent_turn_id == "chat-1"
                for attempt in child_attempts
                if attempt is not None
            )
            model_calls_after_first = len(model.calls)
            replayed_first = await client.post(
                "/api/routedeck/chat",
                json={
                    "request_id": "chat-1",
                    "expected_session_version": created_projection["session_version"],
                    "message": "Show me the catalog and open my cart.",
                },
            )
            assert replayed_first.status_code == 200
            assert [event["event"] for event in _sse_events(replayed_first.text)] == [
                "stream_start",
                "conversation_snapshot",
                "assistant_end",
                "stream_end",
            ]
            assert len(model.calls) == model_calls_after_first
            assert fixture.calls == ["create_cart", "list_products", "get_cart"]
            conflicting_first = await client.post(
                "/api/routedeck/chat",
                json={
                    "request_id": "chat-1",
                    "expected_session_version": created_projection["session_version"],
                    "message": "Use this ID for another request.",
                },
            )
            assert conflicting_first.status_code == 409
            assert conflicting_first.json()["failure"]["code"] == ("request_id_reused")
            assert len(model.calls) == model_calls_after_first

            projection_version = after_tools.projection_version
            second = await client.post(
                "/api/routedeck/chat",
                json={
                    "request_id": "chat-2",
                    "expected_session_version": after_tools.session_version,
                    "message": "Is it empty?",
                },
            )
            assert second.status_code == 200
            second_events = _sse_events(second.text)
            assert _event(second_events, "conversation_snapshot")["turns"] == [
                {
                    "content": "Show me the catalog and open my cart.",
                    "request_id": "chat-1",
                    "role": "user",
                    "turn_id": after_tools.state.conversation[0].turn_id,
                },
                {
                    "content": "Your cart is open.",
                    "request_id": "chat-1",
                    "role": "assistant",
                    "turn_id": after_tools.state.conversation[-1].turn_id,
                },
            ]
            assert _event(second_events, "assistant_delta")["content"] == (
                "Your cart is still empty."
            )
            assert _event(second_events, "stream_end")["status"] == "completed"

            fixture.review_ready = True
            review_session_id = "agent-chat-review"
            review_snapshot = await runtime.services.store.create(
                _review_ready_session(
                    review_session_id,
                    market,
                    runtime.services.app.app,
                )
            )
            client.cookies.clear()
            client.cookies.set("routedeck_guest", review_session_id)
            proposed = await client.post(
                "/api/routedeck/chat",
                json={
                    "request_id": "chat-review",
                    "expected_session_version": review_snapshot.session_version,
                    "message": "Place the order.",
                },
            )
            assert proposed.status_code == 200
            proposed_events = _sse_events(proposed.text)
            assert [event["event"] for event in proposed_events] == [
                "stream_start",
                "conversation_snapshot",
                "user_message",
                "review_required",
                "stream_end",
            ]
            review_event = _event(proposed_events, "review_required")
            assert review_event["operation_id"] == "checkout.place_order"
            assert review_event["status"] == "requires_review"
            assert _event(proposed_events, "stream_end")["status"] == (
                "requires_review"
            )

            staged = await runtime.services.store.load(review_session_id)
            assert staged.state.interaction.phase.value == "idle"
            assert staged.state.interaction.owner is None
            assert staged.state.operation is not None
            pending_review = staged.state.operation.pending_review
            assert pending_review is not None
            assert pending_review.review_id == review_event["review_id"]
            assert [turn.role.value for turn in staged.state.conversation] == [
                "user",
                "tool",
            ]
            assert all(
                turn.request_id == "chat-review"
                and turn.status is ConversationTurnStatus.FINALIZED
                for turn in staged.state.conversation
            )
            assert json.loads(staged.state.conversation[-1].content) == {
                "expires_at": pending_review.expires_at.isoformat(),
                "operation_id": "checkout.place_order",
                "review_id": pending_review.review_id,
                "status": "requires_review",
            }
            assert staged.state.conversation[-1].tool_call.call_id == (
                "place-order-review-agent"
            )
            assert staged.state.conversation[-1].tool_call.name == (
                "checkout.place_order"
            )
            assert staged.state.conversation[-1].tool_status == "success"
            model_calls_after_review = len(model.calls)
            replayed_review = await client.post(
                "/api/routedeck/chat",
                json={
                    "request_id": "chat-review",
                    "expected_session_version": review_snapshot.session_version,
                    "message": "Place the order.",
                },
            )
            assert replayed_review.status_code == 200
            assert [event["event"] for event in _sse_events(replayed_review.text)] == [
                "stream_start",
                "conversation_snapshot",
                "review_required",
                "stream_end",
            ]
            assert len(model.calls) == model_calls_after_review
            assert not any(
                turn.role.value == "assistant" for turn in staged.state.conversation
            )
            inspection_engine = create_engine(database_url)
            try:
                with OrmSession(inspection_engine) as database:
                    lease_count = database.scalar(
                        select(func.count())
                        .select_from(TurnLeaseRow)
                        .where(TurnLeaseRow.session_id == review_session_id)
                    )
            finally:
                inspection_engine.dispose()
            assert lease_count == 0

        completed = await runtime.services.store.load(session_id)
        assert completed.projection_version == projection_version + 2
        assert [turn.role.value for turn in completed.state.conversation] == [
            "user",
            "tool",
            "tool",
            "tool",
            "assistant",
            "user",
            "assistant",
        ]
        assert len(model.calls) == 6
        final_model_history = "\n".join(
            str(message.content) for message in model.calls[4].messages
        )
        assert "Show me the catalog and open my cart." in final_model_history
        assert "Your cart is open." in final_model_history
        assert fixture.private_cart_id not in final_model_history
        assert all(
            attempt is not None
            and attempt.attempt.source.value == "agent"
            and attempt.attempt.parent_turn_id == "chat-1"
            for attempt in child_attempts
        )
    finally:
        await runtime.close()


def _review_ready_session(session_id: str, market: BuyerMarket, app):
    session = create_medusa_session(
        app=app,
        session_id=session_id,
        market=market,
    )
    return session.model_copy(
        update={
            "current": Location(node_id="checkout.review", entry_id=1),
            "private_state": session.private_state.model_copy(
                update={
                    "drafts": (
                        PrivateDraft(
                            form_id="contact-review",
                            field_names=(
                                "billing_choice",
                                "email",
                                "shipping_address",
                            ),
                            revision=1,
                            complete=True,
                        ),
                    ),
                    "entity_bindings": (
                        PrivateEntityBinding(
                            entity_kind="cart",
                            public_handle="cart-review",
                            private_id="private-cart-chat-smoke",
                        ),
                    ),
                }
            ),
            "public_state": session.public_state.model_copy(
                update={
                    "entity_handles": (
                        PublicEntityHandle(
                            entity_kind="cart",
                            handle="cart-review",
                        ),
                    )
                }
            ),
        }
    )


def _sse_events(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    name: str | None = None
    data: dict[str, Any] | None = None
    for line in (*body.splitlines(), ""):
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            value = json.loads(line.removeprefix("data: "))
            assert isinstance(value, dict)
            data = value
        elif not line and name is not None and data is not None:
            events.append({"event": name, "data": data})
            name = None
            data = None
    return events


def _event(events: Sequence[Mapping[str, Any]], name: str) -> Mapping[str, Any]:
    matches = [event["data"] for event in events if event["event"] == name]
    assert len(matches) == 1
    value = matches[0]
    assert isinstance(value, Mapping)
    return value
