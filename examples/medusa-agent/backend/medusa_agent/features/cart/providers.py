from __future__ import annotations

from dataclasses import dataclass

from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.handles import new_opaque_handle
from routedeck_core.supervision.guards import ProviderInvocationContext, ProviderResult

from ...medusa.client.models import CartResult
from ...medusa.client.protocol import MedusaStoreClient
from .models import (
    CartProviderContext,
    CartProviderState,
    EntityHandleFactory,
    project_cart,
)


_BUYER_MARKET_NAMESPACE = "medusa.buyer_market"


@dataclass(frozen=True)
class BuyerMarketProvider:
    """Read the typed buyer market from canonical private session state."""

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        configurations = tuple(
            item
            for item in context.session.private_state.configurations
            if item.namespace == _BUYER_MARKET_NAMESPACE
        )
        if len(configurations) != 1:
            raise RuntimeError(
                "buyer session requires exactly one market configuration"
            )
        fields = {
            field.name: field.value.to_python() for field in configurations[0].fields
        }
        expected = {
            "region_handle",
            "country_code",
            "currency_code",
            "sales_channel_handle",
        }
        if set(fields) != expected or any(
            not isinstance(fields[name], str) or not fields[name] for name in expected
        ):
            raise RuntimeError("buyer market configuration is incomplete or invalid")
        return ProviderResult(
            values=FrozenJsonObject(
                {
                    "region_id": fields["region_handle"],
                    "country_code": fields["country_code"],
                    "currency_code": fields["currency_code"],
                    "sales_channel_id": fields["sales_channel_handle"],
                }
            )
        )


@dataclass(frozen=True)
class CartStateProvider:
    """Refresh the one stored cart from Medusa before every cart operation."""

    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        bindings = tuple(
            binding
            for binding in context.session.private_state.entity_bindings
            if binding.entity_kind == "cart"
        )
        if not bindings:
            return _provider_result(
                CartProviderContext(state=CartProviderState.MISSING)
            )
        if len(bindings) != 1:
            raise RuntimeError("buyer session contains multiple active cart bindings")

        binding = bindings[0]
        result = await self.client.get_cart(binding.private_id)
        if not isinstance(result, CartResult):
            raise TypeError("MedusaStoreClient.get_cart must return CartResult")
        if result.failure is not None:
            return _provider_result(
                CartProviderContext(
                    state=CartProviderState.REFRESH_FAILED,
                    delivery_phase=result.delivery_phase,
                    failure_kind=result.failure.kind,
                    failure_code=result.failure.code,
                    public_message=result.failure.public_message,
                )
            )
        cart = result.value
        if cart is None:
            raise TypeError("Successful CartResult is missing its cart")
        if cart.id.get_secret_value() != binding.private_id:
            raise TypeError("Medusa returned a different cart than the session binding")
        existing_handles: dict[tuple[str, str], str] = {}
        for existing in context.session.private_state.entity_bindings:
            if existing.entity_kind not in {"cart", "line_item"}:
                continue
            key = (existing.entity_kind, existing.private_id)
            previous = existing_handles.get(key)
            if previous is not None and previous != existing.public_handle:
                raise RuntimeError("one Store entity has multiple opaque handles")
            existing_handles[key] = existing.public_handle
        snapshot = project_cart(
            cart,
            new_entity_handle=self.new_entity_handle,
            existing_handles=existing_handles,
        )
        if snapshot.public_cart_handle != binding.public_handle:
            raise TypeError("cart opaque handle changed across authoritative refresh")
        return _provider_result(
            CartProviderContext(
                state=CartProviderState.READY,
                cart=snapshot,
            )
        )


@dataclass(frozen=True)
class CartItemsProvider:
    """Expose only the already-observed opaque line-item handles."""

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        items = []
        for entity in context.session.public_state.entity_handles:
            if entity.entity_kind != "line_item":
                continue
            items.append(
                {
                    "line_item_ref": entity.handle,
                    "values": {
                        value.name: value.value.to_python() for value in entity.values
                    },
                }
            )
        return ProviderResult(values=FrozenJsonObject({"items": items}))


@dataclass(frozen=True)
class CartBindingProvider:
    """Expose the current opaque cart capability without its Store ID."""

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        handles = tuple(
            entity.handle
            for entity in context.session.public_state.entity_handles
            if entity.entity_kind == "cart"
        )
        if len(handles) > 1:
            raise RuntimeError("buyer session contains multiple public cart handles")
        return ProviderResult(
            values=FrozenJsonObject({"cart_ref": handles[0] if handles else None})
        )


def _provider_result(context: CartProviderContext) -> ProviderResult:
    return ProviderResult(values=FrozenJsonObject(context.to_provider_values()))


__all__ = [
    "BuyerMarketProvider",
    "CartBindingProvider",
    "CartItemsProvider",
    "CartStateProvider",
]
