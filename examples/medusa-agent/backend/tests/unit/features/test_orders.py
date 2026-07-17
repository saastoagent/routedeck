from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import SecretStr

from medusa_agent.features.checkout.declarations import CHECKOUT_FACTS_PROVIDER
from medusa_agent.features.checkout.models import (
    CheckoutCartFacts,
    CheckoutFactsContext,
    CheckoutFactsState,
    CheckoutLineFacts,
    CheckoutShippingFacts,
)
from medusa_agent.features.orders.declarations import ORDER_PROVIDER
from medusa_agent.features.orders.handlers import (
    PlaceOrderHandler,
    ReconcileOrderHandler,
)
from medusa_agent.features.orders.models import (
    OrderRecoveryContext,
    actual_order_payload,
    confirmation_projection_from_order,
    verification_fingerprint,
)
from medusa_agent.medusa.client.models import (
    CartShippingMethod,
    Order,
    OrderLineItem,
    OrderPlaced,
    OrderResult,
    PaymentCollection,
    PaymentSession,
    StoreAddress,
)
from routedeck_core.contracts.operations import OperationSource
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.ports.executor import ExecutionContext, ResolvedEntityInput


def test_confirmation_uses_authoritative_item_subtotal() -> None:
    order = Order(
        id=SecretStr("order-private-1"),
        status="completed",
        display_id=42,
        currency_code="eur",
        total=3000,
        subtotal=3000,
        item_subtotal=2000,
        shipping_total=1000,
        tax_total=0,
        discount_total=0,
        items=(
            OrderLineItem(
                id=SecretStr("order-line-private-1"),
                title="T-Shirt",
                quantity=2,
                unit_price=1000,
                total=2000,
            ),
        ),
        shipping_methods=(
            CartShippingMethod(
                shipping_option_id=SecretStr("shipping-private-1"),
                name="Express Shipping",
                amount=1000,
            ),
        ),
    )

    projection = confirmation_projection_from_order(
        order,
        confirmation_handle="order-public-1",
    )

    assert projection.subtotal == 2000
    assert projection.shipping_total == 1000
    assert projection.total == 3000


@pytest.mark.asyncio
async def test_verified_place_order_requests_completed_session_retention() -> None:
    order = _verified_order()
    client = _SuccessfulOrderClient(order)
    outcome = await PlaceOrderHandler(
        client,  # type: ignore[arg-type]
        configured_provider_id="pp_system",
    )({}, _place_order_context(order))

    assert outcome.outcome == "order_created"
    assert outcome.effects.complete_session is True


@pytest.mark.asyncio
async def test_verified_reconciliation_requests_completed_session_retention() -> None:
    order = _verified_order()
    expected = actual_order_payload(order)
    assert expected is not None
    order_ref = "order-public-1"
    context = ExecutionContext(
        session_id="session-1",
        request_id="reconcile-1",
        attempt_id="attempt-reconcile-1",
        node_id="checkout.review",
        source=OperationSource.SURFACE,
        context_fingerprint="context-reconcile-1",
        provider_values=FrozenJsonObject(
            {
                ORDER_PROVIDER.id: OrderRecoveryContext(
                    order_ref=order_ref,
                    verification_fingerprint=verification_fingerprint(expected),
                    contact_form_handle="contact-form-1",
                ).to_provider_values()
            }
        ),
        resolved_entities=(
            ResolvedEntityInput(
                argument_name="order_ref",
                entity_kind="order",
                private_id=order.id,
            ),
        ),
    )

    outcome = await ReconcileOrderHandler(
        _SuccessfulOrderClient(order),  # type: ignore[arg-type]
    )({"order_ref": order_ref}, context)

    assert outcome.outcome == "verified"
    assert outcome.effects.complete_session is True


def _place_order_context(order: Order) -> ExecutionContext:
    actual = actual_order_payload(order)
    assert actual is not None
    facts = CheckoutFactsContext(
        state=CheckoutFactsState.READY,
        cart=CheckoutCartFacts(
            private_cart_id="cart-private-1",
            private_region_id=actual.private_region_id,
            public_cart_handle="cart-public-1",
            currency_code=actual.currency_code,
            items=(
                CheckoutLineFacts(
                    private_variant_id=actual.items[0].private_variant_id,
                    title="T-Shirt",
                    quantity=actual.items[0].quantity,
                    unit_amount=actual.items[0].unit_amount,
                    total=actual.items[0].total,
                ),
            ),
            item_count=actual.items[0].quantity,
            subtotal=actual.subtotal,
            shipping_total=actual.shipping_total,
            tax_total=actual.tax_total,
            discount_total=actual.discount_total,
            total=actual.total,
            contact_saved=True,
            billing_complete=True,
            contact_fingerprint=actual.contact_fingerprint,
            contact_form_handle="contact-form-1",
            shipping_selected=True,
            shipping=CheckoutShippingFacts(
                private_option_id=actual.private_shipping_option_id,
                label=actual.shipping_label,
                amount=actual.shipping_amount,
            ),
            payment_provider_ids=actual.payment_provider_ids,
        ),
    )
    return ExecutionContext(
        session_id="session-1",
        request_id="place-order-1",
        attempt_id="attempt-place-order-1",
        node_id="checkout.review",
        source=OperationSource.SURFACE,
        context_fingerprint="context-place-order-1",
        provider_values=FrozenJsonObject(
            {CHECKOUT_FACTS_PROVIDER.id: facts.to_provider_values()}
        ),
    )


def _verified_order() -> Order:
    address = StoreAddress(
        first_name="Buyer",
        last_name="Example",
        address_1="1 Buyer Street",
        postal_code="SW1A 1AA",
        city="London",
        country_code="gb",
    )
    return Order(
        id=SecretStr("order-private-1"),
        status="completed",
        display_id=42,
        currency_code="gbp",
        region_id=SecretStr("region-private-1"),
        email="buyer@example.com",
        total=3000,
        subtotal=3000,
        item_subtotal=2000,
        shipping_total=1000,
        tax_total=0,
        discount_total=0,
        items=(
            OrderLineItem(
                id=SecretStr("order-line-private-1"),
                variant_id=SecretStr("variant-private-1"),
                title="T-Shirt",
                quantity=2,
                unit_price=1000,
                total=2000,
            ),
        ),
        shipping_methods=(
            CartShippingMethod(
                shipping_option_id=SecretStr("shipping-private-1"),
                name="Express Shipping",
                amount=1000,
            ),
        ),
        shipping_address=address,
        billing_address=address,
        payment_collections=(
            PaymentCollection(
                id=SecretStr("payment-collection-private-1"),
                currency_code="gbp",
                amount=3000,
                payment_sessions=(
                    PaymentSession(
                        id=SecretStr("payment-session-private-1"),
                        provider_id="pp_system",
                    ),
                ),
            ),
        ),
    )


@dataclass(frozen=True)
class _SuccessfulOrderClient:
    order: Order

    async def complete_cart(self, cart_id: str) -> OrderPlaced:
        assert cart_id == "cart-private-1"
        return OrderPlaced(order=self.order)

    async def get_order(self, order_id: str) -> OrderResult:
        assert order_id == self.order.id.get_secret_value()
        return OrderResult.succeeded(self.order)
