from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from routedeck_core.contracts.operations import DeliveryPhase

from ...config import Settings
from .errors import MedusaClientContractError
from .models import (
    Cart,
    CartCompletionRejected,
    CartCompletionUnknown,
    CartResult,
    CheckoutContact,
    CompleteCartResult,
    CompletionError,
    CreateCartRequest,
    CreateCartResult,
    MedusaClientFailure,
    MedusaClientFailureKind,
    Order,
    OrderPlaced,
    OrderResult,
    PaymentCollection,
    PaymentProvider,
    PaymentProvidersResult,
    Product,
    ProductPage,
    ProductPageResult,
    ProductQuery,
    ProductResult,
    Region,
    RegionsResult,
    ShippingOption,
    ShippingOptionsResult,
)


_REGIONS = "/store/regions"
_PRODUCTS = "/store/products"
_CARTS = "/store/carts"
_SHIPPING_OPTIONS = "/store/shipping-options"
_PAYMENT_PROVIDERS = "/store/payment-providers"
_PAYMENT_COLLECTIONS = "/store/payment-collections"
_ORDERS = "/store/orders"

_PRODUCT_FIELDS = (
    "id,handle,title,description,thumbnail,*images,*options,*options.values,"
    "*variants,*variants.options,*variants.calculated_price,+variants.inventory_quantity"
)
_CART_FIELDS = (
    "id,currency_code,region_id,sales_channel_id,email,total,subtotal,item_subtotal,tax_total,"
    "discount_total,shipping_total,*items,+items.total,*shipping_methods,"
    "+shipping_methods.name,*shipping_address,*billing_address,*payment_collection,"
    "*payment_collection.payment_sessions"
)
_ORDER_FIELDS = (
    "id,status,display_id,currency_code,region_id,email,total,subtotal,item_subtotal,tax_total,"
    "discount_total,shipping_total,*items,+items.total,*shipping_methods,"
    "+shipping_methods.name,*shipping_address,*billing_address,*payment_collections,"
    "*payment_collections.payment_sessions"
)


@dataclass(frozen=True)
class TransportFailureEvidence:
    delivery_phase: DeliveryPhase
    failure: MedusaClientFailure


@dataclass(frozen=True)
class _HttpOutcome:
    delivery_phase: DeliveryPhase
    body: dict[str, Any] | None = None
    failure: MedusaClientFailure | None = None


@dataclass(frozen=True)
class StoreCallEvidence:
    """Sanitized adapter-owned coordinates for one measured Store call."""

    operation: str
    method: str
    path_template: str
    transport_kind: str


class MedusaStoreEvidenceSink(Protocol):
    async def record_complete_cart(
        self,
        call: StoreCallEvidence,
        result: CompleteCartResult,
    ) -> None: ...

    async def record_get_order(
        self,
        call: StoreCallEvidence,
        order_id: str,
        result: OrderResult,
    ) -> None: ...


def classify_transport_failure(
    error: httpx.TransportError,
    *,
    request_started: bool,
) -> TransportFailureEvidence:
    """Classify by transport type and send boundary, never exception text."""

    not_sent_types = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
    phase = (
        DeliveryPhase.NOT_SENT
        if isinstance(error, not_sent_types) or not request_started
        else DeliveryPhase.POSSIBLY_SENT
    )
    code = (
        "medusa_connection_failed"
        if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout))
        else "medusa_transport_failed"
    )
    return TransportFailureEvidence(
        delivery_phase=phase,
        failure=MedusaClientFailure(
            kind=MedusaClientFailureKind.TRANSPORT,
            code=code,
            public_message="The commerce service could not be reached.",
        ),
    )


class HttpMedusaStoreClient:
    """The sole owner of Medusa Store URLs, headers, HTTP, and wire schemas."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        evidence_sink: MedusaStoreEvidenceSink | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._evidence_sink = evidence_sink
        self._base_url = str(settings.medusa_base_url).rstrip("/")
        self._headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-publishable-api-key": settings.medusa_publishable_key.get_secret_value(),
        }

    async def list_regions(self) -> RegionsResult:
        outcome = await self._request("GET", _REGIONS)
        if outcome.failure is not None:
            return RegionsResult.failed(
                delivery_phase=outcome.delivery_phase,
                failure=outcome.failure,
            )
        try:
            regions = tuple(
                Region.model_validate(item)
                for item in _required_list(outcome.body, "regions")
            )
        except (ValidationError, TypeError, ValueError):
            return RegionsResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=_protocol_failure("regions_schema_invalid"),
            )
        return RegionsResult.succeeded(regions)

    async def list_products(self, query: ProductQuery) -> ProductPageResult:
        params: dict[str, Any] = {
            "region_id": query.region_id,
            "limit": query.limit,
            "offset": query.offset,
            "fields": _PRODUCT_FIELDS,
        }
        if query.query is not None:
            params["q"] = query.query
        if query.handle is not None:
            params["handle"] = query.handle
        outcome = await self._request("GET", _PRODUCTS, params=params)
        if outcome.failure is not None:
            return ProductPageResult.failed(
                delivery_phase=outcome.delivery_phase,
                failure=outcome.failure,
            )
        try:
            body = _required_body(outcome.body)
            page = ProductPage(
                products=tuple(
                    Product.model_validate(item)
                    for item in _required_list(body, "products")
                ),
                count=_required_int(body, "count"),
                offset=_required_int(body, "offset"),
                limit=_required_int(body, "limit"),
            )
        except (ValidationError, TypeError, ValueError):
            return ProductPageResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=_protocol_failure("products_schema_invalid"),
            )
        return ProductPageResult.succeeded(page)

    async def get_product(self, handle: str, region_id: str) -> ProductResult:
        if not handle or not region_id:
            raise MedusaClientContractError("handle and region_id must be non-empty")
        result = await self.list_products(
            ProductQuery(region_id=region_id, handle=handle, limit=2)
        )
        if result.failure is not None:
            return ProductResult.failed(
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        if result.value is None:
            raise RuntimeError("Successful product page result is missing its value")
        if not result.value.products:
            return ProductResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=MedusaClientFailure(
                    kind=MedusaClientFailureKind.BUSINESS,
                    code="product_not_found",
                    public_message="That product is unavailable.",
                ),
            )
        if len(result.value.products) != 1:
            return ProductResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=_protocol_failure("product_handle_not_unique"),
            )
        return ProductResult.succeeded(result.value.products[0])

    async def create_cart(self, request: CreateCartRequest) -> CreateCartResult:
        outcome = await self._request(
            "POST",
            _CARTS,
            params={"fields": _CART_FIELDS},
            json_body={
                "region_id": request.region_id,
                "sales_channel_id": request.sales_channel_id,
            },
        )
        if outcome.failure is not None:
            return CreateCartResult.failed(
                delivery_phase=outcome.delivery_phase,
                failure=outcome.failure,
            )
        cart = _parse_resource(outcome.body, "cart", Cart, "cart_schema_invalid")
        if isinstance(cart, MedusaClientFailure):
            return CreateCartResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=cart,
            )
        return CreateCartResult.succeeded(cart)

    async def get_cart(self, cart_id: str) -> CartResult:
        _require_identifier(cart_id, "cart_id")
        outcome = await self._request(
            "GET",
            f"{_CARTS}/{cart_id}",
            params={"fields": _CART_FIELDS},
        )
        return _cart_result(outcome, key="cart")

    async def add_line_item(
        self,
        cart_id: str,
        variant_id: str,
        quantity: int,
    ) -> CartResult:
        _require_identifier(cart_id, "cart_id")
        _require_identifier(variant_id, "variant_id")
        if quantity < 1:
            raise MedusaClientContractError("quantity must be positive")
        outcome = await self._request(
            "POST",
            f"{_CARTS}/{cart_id}/line-items",
            params={"fields": _CART_FIELDS},
            json_body={"variant_id": variant_id, "quantity": quantity},
        )
        return _cart_result(outcome, key="cart")

    async def update_line_item(
        self,
        cart_id: str,
        line_id: str,
        quantity: int,
    ) -> CartResult:
        _require_identifier(cart_id, "cart_id")
        _require_identifier(line_id, "line_id")
        if quantity < 0:
            raise MedusaClientContractError("quantity cannot be negative")
        outcome = await self._request(
            "POST",
            f"{_CARTS}/{cart_id}/line-items/{line_id}",
            params={"fields": _CART_FIELDS},
            json_body={"quantity": quantity},
        )
        return _cart_result(outcome, key="cart")

    async def remove_line_item(self, cart_id: str, line_id: str) -> CartResult:
        _require_identifier(cart_id, "cart_id")
        _require_identifier(line_id, "line_id")
        outcome = await self._request(
            "DELETE",
            f"{_CARTS}/{cart_id}/line-items/{line_id}",
            params={"fields": _CART_FIELDS},
        )
        return _cart_result(outcome, key="parent")

    async def set_checkout_contact(
        self,
        cart_id: str,
        contact: CheckoutContact,
    ) -> CartResult:
        _require_identifier(cart_id, "cart_id")
        outcome = await self._request(
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
        return _cart_result(outcome, key="cart")

    async def list_shipping_options(
        self,
        cart_id: str,
    ) -> ShippingOptionsResult:
        _require_identifier(cart_id, "cart_id")
        outcome = await self._request(
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
                for item in _required_list(outcome.body, "shipping_options")
            )
        except (ValidationError, TypeError, ValueError):
            return ShippingOptionsResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=_protocol_failure("shipping_options_schema_invalid"),
            )
        return ShippingOptionsResult.succeeded(options)

    async def set_shipping_option(
        self,
        cart_id: str,
        option_id: str,
    ) -> CartResult:
        _require_identifier(cart_id, "cart_id")
        _require_identifier(option_id, "option_id")
        outcome = await self._request(
            "POST",
            f"{_CARTS}/{cart_id}/shipping-methods",
            params={"fields": _CART_FIELDS},
            json_body={"option_id": option_id},
        )
        return _cart_result(outcome, key="cart")

    async def list_payment_providers(
        self,
        region_id: str,
    ) -> PaymentProvidersResult:
        _require_identifier(region_id, "region_id")
        outcome = await self._request(
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
                for item in _required_list(outcome.body, "payment_providers")
            )
        except (ValidationError, TypeError, ValueError):
            return PaymentProvidersResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=_protocol_failure("payment_providers_schema_invalid"),
            )
        return PaymentProvidersResult.succeeded(providers)

    async def initialize_payment(
        self,
        cart: Cart,
        provider_id: str,
    ) -> CartResult:
        _require_identifier(provider_id, "provider_id")
        cart_id = cart.id.get_secret_value()
        collection = cart.payment_collection
        prior_write = False
        if collection is None:
            collection_outcome = await self._request(
                "POST",
                _PAYMENT_COLLECTIONS,
                json_body={"cart_id": cart_id},
            )
            if collection_outcome.failure is not None:
                return CartResult.failed(
                    delivery_phase=collection_outcome.delivery_phase,
                    failure=collection_outcome.failure,
                )
            parsed = _parse_resource(
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

        session_outcome = await self._request(
            "POST",
            f"{_PAYMENT_COLLECTIONS}/{collection.id.get_secret_value()}/payment-sessions",
            json_body={"provider_id": provider_id},
        )
        if session_outcome.failure is not None:
            return CartResult.failed(
                delivery_phase=_promote_after_write(
                    session_outcome.delivery_phase, prior_write=prior_write
                ),
                failure=session_outcome.failure,
            )
        refreshed = await self.get_cart(cart_id)
        if refreshed.failure is not None:
            return CartResult.failed(
                delivery_phase=DeliveryPhase.POSSIBLY_SENT,
                failure=refreshed.failure,
            )
        return refreshed

    async def complete_cart(self, cart_id: str) -> CompleteCartResult:
        _require_identifier(cart_id, "cart_id")
        outcome = await self._request(
            "POST",
            f"{_CARTS}/{cart_id}/complete",
            params={"fields": _ORDER_FIELDS},
        )
        if outcome.failure is not None:
            return await self._record_complete_cart(
                CartCompletionUnknown(
                    delivery_phase=outcome.delivery_phase,
                    failure=outcome.failure,
                )
            )
        body = _required_body(outcome.body)
        response_type = body.get("type")
        if response_type == "order":
            parsed = _parse_resource(body, "order", Order, "order_schema_invalid")
            if isinstance(parsed, MedusaClientFailure):
                return await self._record_complete_cart(
                    CartCompletionUnknown(
                        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                        failure=parsed,
                    )
                )
            return await self._record_complete_cart(OrderPlaced(order=parsed))
        if response_type == "cart":
            parsed = _parse_resource(body, "cart", Cart, "cart_schema_invalid")
            error = body.get("error")
            error_type = error.get("type") if isinstance(error, Mapping) else None
            if isinstance(parsed, MedusaClientFailure) or not isinstance(
                error_type, str
            ):
                return await self._record_complete_cart(
                    CartCompletionUnknown(
                        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                        failure=(
                            parsed
                            if isinstance(parsed, MedusaClientFailure)
                            else _protocol_failure("completion_error_schema_invalid")
                        ),
                    ),
                )
            return await self._record_complete_cart(
                CartCompletionRejected(
                    cart=parsed,
                    error=CompletionError(
                        code=error_type,
                        public_message="The cart could not be completed.",
                    ),
                ),
            )
        return await self._record_complete_cart(
            CartCompletionUnknown(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=_protocol_failure("completion_discriminator_invalid"),
            )
        )

    async def get_order(self, order_id: str) -> OrderResult:
        _require_identifier(order_id, "order_id")
        outcome = await self._request(
            "GET",
            f"{_ORDERS}/{order_id}",
            params={"fields": _ORDER_FIELDS},
        )
        if outcome.failure is not None:
            return await self._record_get_order(
                order_id,
                OrderResult.failed(
                    delivery_phase=outcome.delivery_phase,
                    failure=outcome.failure,
                ),
            )
        parsed = _parse_resource(outcome.body, "order", Order, "order_schema_invalid")
        if isinstance(parsed, MedusaClientFailure):
            return await self._record_get_order(
                order_id,
                OrderResult.failed(
                    delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                    failure=parsed,
                ),
            )
        return await self._record_get_order(order_id, OrderResult.succeeded(parsed))

    async def _record_complete_cart(
        self,
        result: CompleteCartResult,
    ) -> CompleteCartResult:
        if self._evidence_sink is not None:
            await self._evidence_sink.record_complete_cart(
                StoreCallEvidence(
                    operation="complete_cart",
                    method="POST",
                    path_template=f"{_CARTS}/{{cart_id}}/complete",
                    transport_kind=(
                        "network" if self._transport is None else "injected"
                    ),
                ),
                result,
            )
        return result

    async def _record_get_order(
        self,
        order_id: str,
        result: OrderResult,
    ) -> OrderResult:
        if self._evidence_sink is not None:
            await self._evidence_sink.record_get_order(
                StoreCallEvidence(
                    operation="get_order",
                    method="GET",
                    path_template=f"{_ORDERS}/{{order_id}}",
                    transport_kind=(
                        "network" if self._transport is None else "injected"
                    ),
                ),
                order_id,
                result,
            )
        return result

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> _HttpOutcome:
        request_started = False
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._settings.medusa_timeout_seconds,
                transport=self._transport,
            ) as client:
                request_started = True
                response = await client.request(
                    method,
                    path,
                    params=params,
                    json=dict(json_body) if json_body is not None else None,
                )
        except httpx.TransportError as error:
            evidence = classify_transport_failure(
                error,
                request_started=request_started,
            )
            return _HttpOutcome(
                delivery_phase=evidence.delivery_phase,
                failure=evidence.failure,
            )

        parsed_body: dict[str, Any] | None = None
        try:
            candidate = response.json()
            if isinstance(candidate, dict):
                parsed_body = candidate
        except ValueError:
            parsed_body = None

        if not 200 <= response.status_code < 300:
            return _HttpOutcome(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=_status_failure(response.status_code, parsed_body),
            )
        if parsed_body is None:
            return _HttpOutcome(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=_protocol_failure("response_json_invalid"),
            )
        return _HttpOutcome(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            body=parsed_body,
        )


def _cart_result(outcome: _HttpOutcome, *, key: str) -> CartResult:
    if outcome.failure is not None:
        return CartResult.failed(
            delivery_phase=outcome.delivery_phase,
            failure=outcome.failure,
        )
    parsed = _parse_resource(outcome.body, key, Cart, "cart_schema_invalid")
    if isinstance(parsed, MedusaClientFailure):
        return CartResult.failed(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            failure=parsed,
        )
    return CartResult.succeeded(parsed)


def _parse_resource(
    body: dict[str, Any] | None,
    key: str,
    model: type[Any],
    failure_code: str,
) -> Any | MedusaClientFailure:
    try:
        value = _required_body(body).get(key)
        if not isinstance(value, Mapping):
            raise TypeError(key)
        return model.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        return _protocol_failure(failure_code)


def _required_body(body: dict[str, Any] | None) -> dict[str, Any]:
    if body is None:
        raise TypeError("response body")
    return body


def _required_list(body: dict[str, Any] | None, key: str) -> list[Any]:
    value = _required_body(body).get(key)
    if not isinstance(value, list):
        raise TypeError(key)
    if any(not isinstance(item, Mapping) for item in value):
        raise TypeError(key)
    return value


def _required_int(body: Mapping[str, Any], key: str) -> int:
    value = body.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(key)
    return value


def _require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise MedusaClientContractError(f"{name} must be a non-empty string")


def _promote_after_write(
    phase: DeliveryPhase,
    *,
    prior_write: bool,
) -> DeliveryPhase:
    if prior_write and phase is DeliveryPhase.NOT_SENT:
        return DeliveryPhase.POSSIBLY_SENT
    return phase


def _protocol_failure(code: str) -> MedusaClientFailure:
    return MedusaClientFailure(
        kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
        code=code,
        public_message="The commerce service returned an invalid response.",
    )


def _status_failure(
    status_code: int,
    body: Mapping[str, Any] | None,
) -> MedusaClientFailure:
    structured_code = None
    if body is not None:
        candidate = body.get("type") or body.get("code")
        if isinstance(candidate, str) and candidate:
            structured_code = candidate
    if status_code >= 500:
        return MedusaClientFailure(
            kind=MedusaClientFailureKind.TRANSPORT,
            code=structured_code or "medusa_unavailable",
            public_message="The commerce service is unavailable.",
        )
    return MedusaClientFailure(
        kind=MedusaClientFailureKind.BUSINESS,
        code=structured_code or f"medusa_http_{status_code}",
        public_message="The commerce service rejected the request.",
    )


__all__ = [
    "HttpMedusaStoreClient",
    "MedusaStoreEvidenceSink",
    "StoreCallEvidence",
    "TransportFailureEvidence",
    "classify_transport_failure",
]
