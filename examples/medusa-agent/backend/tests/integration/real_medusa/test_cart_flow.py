from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from medusa_agent.composition import compile_medusa_app_spec
from medusa_agent.runtime_factory import open_persistent_medusa_runtime
from medusa_agent.config import Settings
from medusa_agent.features.cart.feature import CART_SUMMARY
from medusa_agent.medusa.client import HttpMedusaStoreClient
from medusa_agent.session import BuyerMarket
from routedeck_core.app import ContextProvider, Guard, OperationHandler
from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.operations import (
    GuardRef,
    OperationDisposition,
    OperationOutcome,
    OperationRef,
    OperationRequest,
    OperationSource,
    ProviderRef,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.ports.executor import ExecutionContext
from routedeck_core.supervision.guards import (
    GuardDecision,
    GuardInvocationContext,
    ProviderInvocationContext,
    ProviderResult,
)


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
}


@dataclass
class _CountingClient:
    delegate: HttpMedusaStoreClient
    calls: list[str] = field(default_factory=list)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    async def create_cart(self, request: Any) -> Any:
        self.calls.append("create_cart")
        return await self.delegate.create_cart(request)

    async def add_line_item(
        self,
        cart_id: str,
        variant_id: str,
        quantity: int,
    ) -> Any:
        self.calls.append("add_line_item")
        return await self.delegate.add_line_item(cart_id, variant_id, quantity)

    async def update_line_item(
        self,
        cart_id: str,
        line_id: str,
        quantity: int,
    ) -> Any:
        self.calls.append("update_line_item")
        return await self.delegate.update_line_item(cart_id, line_id, quantity)

    async def remove_line_item(self, cart_id: str, line_id: str) -> Any:
        self.calls.append("remove_line_item")
        return await self.delegate.remove_line_item(cart_id, line_id)


class _UnexpectedHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        del arguments, context
        raise AssertionError("an unrelated operation executed in the cart flow")


class _UnexpectedProvider:
    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        del context
        raise AssertionError("an unrelated provider executed in the cart flow")


class _UnexpectedGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        del context
        raise AssertionError("an unrelated guard executed in the cart flow")


@dataclass(frozen=True)
class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class _RecordingNotifier:
    events: list[RouteDeckEvent] = field(default_factory=list)

    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        del session_id
        self.events.extend(events)


@pytest.mark.asyncio
async def test_real_runner_cart_create_add_update_remove_and_reopen(
    tmp_path: Path,
) -> None:
    settings = Settings.from_env()
    client = _CountingClient(HttpMedusaStoreClient(settings))
    regions = await client.list_regions()
    assert regions.failure is None and regions.value is not None
    region = next(
        candidate
        for candidate in regions.value
        if candidate.id.get_secret_value() == settings.medusa_region_id
    )
    assert region.countries
    market = BuyerMarket(
        region_handle=settings.medusa_region_id,
        country_code=region.countries[0].iso_2.lower(),
        currency_code=region.currency_code,
        sales_channel_handle=settings.medusa_sales_channel_id,
    )

    compiled = compile_medusa_app_spec()
    handlers: dict[OperationRef, OperationHandler] = {
        operation.ref: _UnexpectedHandler()
        for operation in compiled.operations.values()
        if operation.id not in _OWNED_OPERATION_IDS
    }
    providers: dict[ProviderRef, ContextProvider] = {
        provider.ref: _UnexpectedProvider()
        for provider in compiled.providers.values()
        if provider.id not in _OWNED_PROVIDER_IDS
    }
    guards: dict[GuardRef, Guard] = {
        guard.ref: _UnexpectedGuard()
        for guard in compiled.guards.values()
        if guard.id not in _OWNED_GUARD_IDS
    }
    notifier = _RecordingNotifier()
    session_id = f"cart-flow-{uuid4().hex}"
    runtime = await open_persistent_medusa_runtime(
        database_url=(
            "sqlite+pysqlite:///"
            + (tmp_path / "cart-flow.sqlite").as_posix()
        ),
        encryption_key=settings.routedeck_state_encryption_key.get_secret_value(),
        instance_id=f"cart-flow-instance-{uuid4().hex}",
        client=client,  # type: ignore[arg-type]
        configured_payment_provider_id=settings.medusa_payment_provider_id,
        handlers=handlers,
        providers=providers,
        guards=guards,
        clock=_SystemClock(),
        notifier=notifier,
        id_factory=lambda kind: f"{kind}-{uuid4().hex}",
        review_ttl=timedelta(minutes=10),
        default_session_id=session_id,
        market=market,
    )
    try:
        snapshot = await runtime.create_session()
        cart_binding = next(
            binding
            for binding in snapshot.state.private_state.entity_bindings
            if binding.entity_kind == "cart"
        )
        private_cart_id = cart_binding.private_id
        assert client.calls.count("create_cart") == 1

        await _run(runtime, "catalog.list", "catalog-list-1")
        snapshot = await runtime.load_session()
        product_ref = next(
            entity.handle
            for entity in snapshot.state.public_state.entity_handles
            if entity.entity_kind == "product"
        )
        await _run(
            runtime,
            "catalog.open_product",
            "catalog-open-1",
            {"product_ref": product_ref},
        )
        snapshot = await runtime.load_session()
        variant_ref = next(
            entity.handle
            for entity in snapshot.state.public_state.entity_handles
            if entity.entity_kind == "variant"
        )

        add_request = await _request(
            runtime,
            "cart.add_item",
            "cart-add-1",
            {"variant_ref": variant_ref, "quantity": 1},
        )
        first_add = await runtime.runner.run(add_request)
        replayed_add = await runtime.runner.run(add_request)
        assert first_add == replayed_add
        assert first_add.disposition is OperationDisposition.COMPLETED
        assert client.calls.count("add_line_item") == 1

        await _run(runtime, "cart.open", "cart-open-1")
        snapshot = await runtime.load_session()
        line_ref = next(
            entity.handle
            for entity in snapshot.state.public_state.entity_handles
            if entity.entity_kind == "line_item"
        )
        await _run(
            runtime,
            "cart.update_item",
            "cart-update-1",
            {"line_item_ref": line_ref, "quantity": 2},
        )
        assert client.calls.count("update_line_item") == 1
        updated = await runtime.load_session()
        updated_cart = _cart_surface(updated.state)
        assert updated_cart["items"][0]["quantity"] == 2
        assert updated_cart["items"][0]["line_total"] >= 0
        assert updated_cart["total"] >= updated_cart["subtotal"]

        await _run(
            runtime,
            "cart.remove_item",
            "cart-remove-1",
            {"line_item_ref": line_ref},
        )
        assert client.calls.count("remove_line_item") == 1
        await _run(runtime, "cart.open", "cart-reopen-1")
        reopened = await runtime.load_session()
        reopened_cart = _cart_surface(reopened.state)
        assert reopened_cart["items"] == []
        assert not any(
            binding.entity_kind == "line_item"
            for binding in reopened.state.private_state.entity_bindings
        )

        public_json = reopened.state.public_state.model_dump_json()
        assert private_cart_id not in public_json
        assert all(
            private_cart_id not in event.model_dump_json() for event in notifier.events
        )
    finally:
        await runtime.close()


async def _request(
    runtime: Any,
    operation_id: str,
    request_id: str,
    arguments: Mapping[str, Any] | None = None,
) -> OperationRequest:
    snapshot = await runtime.load_session()
    return OperationRequest(
        session_id=snapshot.session_id,
        request_id=request_id,
        expected_session_version=snapshot.session_version,
        operation_id=operation_id,
        source=OperationSource.SYSTEM,
        arguments=FrozenJsonObject(dict(arguments or {})),
    )


async def _run(
    runtime: Any,
    operation_id: str,
    request_id: str,
    arguments: Mapping[str, Any] | None = None,
) -> Any:
    result = await runtime.runner.run(
        await _request(runtime, operation_id, request_id, arguments)
    )
    assert result.disposition is OperationDisposition.COMPLETED, result
    return result


def _cart_surface(session: Any) -> dict[str, Any]:
    surface = next(
        item
        for item in session.public_state.surface_state
        if item.surface_id == CART_SUMMARY.id
    )
    return {value.name: value.value.to_python() for value in surface.values}
