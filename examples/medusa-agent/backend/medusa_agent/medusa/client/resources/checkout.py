from __future__ import annotations

from pydantic import ValidationError

from routedeck_core.contracts.operations import DeliveryPhase

from ..models import (
    Cart,
    CartResult,
    CheckoutContact,
    MedusaClientFailure,
    PaymentCollection,
    PaymentProvider,
    PaymentProvidersResult,
    ShippingOption,
    ShippingOptionsResult,
)
from ..transport import protocol_failure
from ..wire import (
    cart_result,
    parse_resource,
    promote_after_write,
    require_identifier,
    required_list,
)
from .base import MedusaResourceClient
from .cart import CartResource


_CARTS = "/store/carts"
_SHIPPING_OPTIONS = "/store/shipping-options"
_PAYMENT_PROVIDERS = "/store/payment-providers"
_PAYMENT_COLLECTIONS = "/store/payment-collections"
_CART_FIELDS = (
    "id,currency_code,region_id,sales_channel_id,email,total,subtotal,item_subtotal,tax_total,"
    "discount_total,shipping_total,*items,+items.total,*shipping_methods,"
    "+shipping_methods.name,*shipping_address,*billing_address,*payment_collection,"
    "*payment_collection.payment_sessions"
)


class CheckoutResource:
    def __init__(
        self,
        base: MedusaResourceClient,
        cart: CartResource,
    ) -> None:
        self._base = base
        self._cart = cart

    async def set_checkout_contact(
        self,
        cart_id: str,
        contact: CheckoutContact,
    ) -> CartResult:
        require_identifier(cart_id, "cart_id")
        outcome = await self._base.request(
            "POST",
            f"{_CARTS}/{cart_id}",
            params={"fields": _CART_FIELDS},
            json_body={
                "email": contact.email,
                "shipping_address": contact.shipping_address.model_dump(
                    mode="json", exclude_none=True
                ),
                "billing_address": contact.billing_address.model_dump(
                    mode="json", exclude_none=True
                ),
            },
        )
        return cart_result(outcome, key="cart")

    async def list_shipping_options(
        self,
        cart_id: str,
    ) -> ShippingOptionsResult:
        require_identifier(cart_id, "cart_id")
        outcome = await self._base.request(
            "GET",
            _SHIPPING_OPTIONS,
            params={"cart_id": cart_id},
        )
        if outcome.failure is not None:
            return ShippingOptionsResult.failed(
                delivery_phase=outcome.delivery_phase,
                failure=outcome.failure,
            )
        try:
            options = tuple(
                ShippingOption.model_validate(item)
                for item in required_list(outcome.body, "shipping_options")
            )
        except (ValidationError, TypeError, ValueError):
            return ShippingOptionsResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=protocol_failure("shipping_options_schema_invalid"),
            )
        return ShippingOptionsResult.succeeded(options)

    async def set_shipping_option(
        self,
        cart_id: str,
        option_id: str,
    ) -> CartResult:
        require_identifier(cart_id, "cart_id")
        require_identifier(option_id, "option_id")
        outcome = await self._base.request(
            "POST",
            f"{_CARTS}/{cart_id}/shipping-methods",
            params={"fields": _CART_FIELDS},
            json_body={"option_id": option_id},
        )
        return cart_result(outcome, key="cart")

    async def list_payment_providers(
        self,
        region_id: str,
    ) -> PaymentProvidersResult:
        require_identifier(region_id, "region_id")
        outcome = await self._base.request(
            "GET",
            _PAYMENT_PROVIDERS,
            params={"region_id": region_id},
        )
        if outcome.failure is not None:
            return PaymentProvidersResult.failed(
                delivery_phase=outcome.delivery_phase,
                failure=outcome.failure,
            )
        try:
            providers = tuple(
                PaymentProvider.model_validate(item)
                for item in required_list(outcome.body, "payment_providers")
            )
        except (ValidationError, TypeError, ValueError):
            return PaymentProvidersResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=protocol_failure("payment_providers_schema_invalid"),
            )
        return PaymentProvidersResult.succeeded(providers)

    async def initialize_payment(
        self,
        cart: Cart,
        provider_id: str,
    ) -> CartResult:
        require_identifier(provider_id, "provider_id")
        cart_id = cart.id.get_secret_value()
        collection = cart.payment_collection
        prior_write = False
        if collection is None:
            collection_outcome = await self._base.request(
                "POST",
                _PAYMENT_COLLECTIONS,
                json_body={"cart_id": cart_id},
            )
            if collection_outcome.failure is not None:
                return CartResult.failed(
                    delivery_phase=collection_outcome.delivery_phase,
                    failure=collection_outcome.failure,
                )
            parsed = parse_resource(
                collection_outcome.body,
                "payment_collection",
                PaymentCollection,
                "payment_collection_schema_invalid",
            )
            if isinstance(parsed, MedusaClientFailure):
                return CartResult.failed(
                    delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                    failure=parsed,
                )
            collection = parsed
            prior_write = True

        session_outcome = await self._base.request(
            "POST",
            f"{_PAYMENT_COLLECTIONS}/{collection.id.get_secret_value()}/payment-sessions",
            json_body={"provider_id": provider_id},
        )
        if session_outcome.failure is not None:
            return CartResult.failed(
                delivery_phase=promote_after_write(
                    session_outcome.delivery_phase,
                    prior_write=prior_write,
                ),
                failure=session_outcome.failure,
            )
        refreshed = await self._cart.get_cart(cart_id)
        if refreshed.failure is not None:
            return CartResult.failed(
                delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                failure=refreshed.failure,
            )
        return refreshed


__all__ = ["CheckoutResource"]
