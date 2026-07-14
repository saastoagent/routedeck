from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import SecretStr, ValidationError

from medusa_agent.features.cart.feature import CART_STATE_PROVIDER
from medusa_agent.features.cart.operations import AddCartItemHandler
from medusa_agent.features.cart.models import (
    CartProviderContext,
    CartProviderState,
    project_cart,
    snapshot_entity_handles,
)
from medusa_agent.medusa.client.models import Cart, CartLineItem, CartResult
from routedeck_core.contracts.operations import OperationSource
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.ports.executor import ExecutionContext, ResolvedEntityInput


def _cart(*, quantity: int, include_line: bool = True) -> Cart:
    item_subtotal = 2500 * quantity if include_line else 0
    shipping_total = 500 if include_line else 0
    items = (
        (
            CartLineItem(
                id=SecretStr("line-private-1"),
                variant_id=SecretStr("variant-private-1"),
                title="Medusa T-Shirt",
                product_title="Medusa T-Shirt",
                variant_title="M / Black",
                quantity=quantity,
                unit_price=2500,
                total=2500 * quantity,
            ),
        )
        if include_line
        else ()
    )
    return Cart(
        id=SecretStr("cart-private-1"),
        currency_code="usd",
        region_id=SecretStr("region-private-1"),
        total=item_subtotal + shipping_total,
        subtotal=item_subtotal + shipping_total,
        item_subtotal=item_subtotal,
        shipping_total=shipping_total,
        items=items,
    )


def test_project_cart_preserves_handles_and_authoritative_totals() -> None:
    handles = iter(("cart-public-1", "line-public-1", "unused-public"))
    first = project_cart(_cart(quantity=1), new_entity_handle=lambda: next(handles))
    refreshed = project_cart(
        _cart(quantity=3),
        new_entity_handle=lambda: next(handles),
        existing_handles=snapshot_entity_handles(first),
    )

    assert refreshed.public_cart_handle == "cart-public-1"
    assert refreshed.line_bindings[0].public_handle == "line-public-1"
    assert refreshed.projection.items[0].quantity == 3
    assert refreshed.projection.items[0].line_total == 7500
    assert refreshed.projection.subtotal == 7500
    assert refreshed.projection.shipping_total == 500
    assert refreshed.projection.total == 8000


def test_cart_requires_authoritative_item_subtotal() -> None:
    with pytest.raises(ValidationError, match="item_subtotal"):
        Cart.model_validate(
            {
                "id": "cart-private-1",
                "currency_code": "usd",
                "region_id": "region-private-1",
            }
        )


@dataclass
class _AddClient:
    result: CartResult
    calls: list[tuple[str, str, int]] = field(default_factory=list)

    async def add_line_item(
        self,
        cart_id: str,
        variant_id: str,
        quantity: int,
    ) -> CartResult:
        self.calls.append((cart_id, variant_id, quantity))
        return self.result


@pytest.mark.asyncio
async def test_add_uses_only_resolved_private_ids_and_journals_line_effects() -> None:
    current = project_cart(
        _cart(quantity=0, include_line=False),
        new_entity_handle=lambda: "cart-public-1",
    )
    client = _AddClient(CartResult.succeeded(_cart(quantity=2)))
    context = ExecutionContext(
        session_id="session-1",
        request_id="add-1",
        attempt_id="attempt-1",
        node_id="catalog.product",
        source=OperationSource.SURFACE,
        context_fingerprint="context-1",
        provider_values=FrozenJsonObject(
            {
                CART_STATE_PROVIDER.id: CartProviderContext(
                    state=CartProviderState.READY,
                    cart=current,
                ).to_provider_values()
            }
        ),
        resolved_entities=(
            ResolvedEntityInput(
                argument_name="variant_ref",
                entity_kind="variant",
                private_id=SecretStr("variant-private-1"),
            ),
        ),
    )

    outcome = await AddCartItemHandler(
        client,  # type: ignore[arg-type]
        new_entity_handle=lambda: "line-public-1",
    )(
        {"variant_ref": "variant-public-1", "quantity": 2},
        context,
    )

    assert client.calls == [("cart-private-1", "variant-private-1", 2)]
    assert outcome.outcome == "added"
    line_effect = next(
        effect
        for effect in outcome.effects.replace_entities
        if effect.entity_kind == "line_item"
    )
    assert line_effect.bindings[0].public.handle == "line-public-1"
    assert line_effect.bindings[0].private_id.get_secret_value() == "line-private-1"
    assert line_effect.bindings[0].allowed_operation_ids == ()
    assert outcome.effects.surface_updates == ()
