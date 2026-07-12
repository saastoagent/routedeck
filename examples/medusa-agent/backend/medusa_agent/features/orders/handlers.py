from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
    ExactRouteParameter,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.failures import (
    FailureKind,
    FailureSafeDetails,
    RouteDeckFailure,
)
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import (
    FrozenJson,
    FrozenJsonObject,
    PublicEntityHandle,
    PublicValue,
)
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ...medusa.client.models import (
    CartCompletionRejected,
    CartCompletionUnknown,
    MedusaClientFailure,
    MedusaClientFailureKind,
    Order,
    OrderPlaced,
    OrderResult,
)
from ...medusa.client.protocol import MedusaStoreClient
from ..catalog.feature import (
    CATALOG_PRODUCTS_PROVIDER,
    CONTINUE_SHOPPING,
    OPEN_PRODUCT,
    PRODUCT_GRID,
)
from ..catalog.models import CatalogCollectionProviderValue
from ..checkout.feature import (
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_RECOVERY,
    PLACE_ORDER,
)
from ..checkout.models import CheckoutFactsContext, CheckoutFactsState
from .feature import ORDER_CONFIRMATION, ORDER_PROVIDER, RECONCILE_ORDER
from .models import (
    OrderConfirmationProjection,
    OrderRecoveryContext,
    confirmation_projection,
    confirmation_projection_from_order,
    expected_order_payload,
    order_matches_fingerprint,
    verification_fingerprint,
)


_FAILURE_KINDS = {
    MedusaClientFailureKind.TRANSPORT: FailureKind.TRANSPORT,
    MedusaClientFailureKind.PROVIDER_PROTOCOL: FailureKind.PROVIDER_PROTOCOL,
    MedusaClientFailureKind.BUSINESS: FailureKind.BUSINESS,
}


@dataclass(frozen=True)
class PlaceOrderHandler:
    client: MedusaStoreClient
    configured_provider_id: str

    def __post_init__(self) -> None:
        if not self.configured_provider_id:
            raise ValueError("configured payment provider ID must be non-empty")

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        if arguments:
            raise ValueError(f"{PLACE_ORDER.id} accepts no arguments")
        reviewed_cart = _reviewed_cart(context)
        expected = expected_order_payload(
            reviewed_cart,
            configured_provider_id=self.configured_provider_id,
        )
        if reviewed_cart.contact_form_handle is None:
            raise RuntimeError("place order requires a completed private contact form")
        expected_fingerprint = verification_fingerprint(expected)

        completion = await self.client.complete_cart(reviewed_cart.private_cart_id)
        if isinstance(completion, CartCompletionRejected):
            return _business_failure(
                context=context,
                operation_id=PLACE_ORDER.id,
                code=completion.error.code,
                message=completion.error.public_message,
            )
        if isinstance(completion, CartCompletionUnknown):
            return _unknown_failure(
                context=context,
                operation_id=PLACE_ORDER.id,
                delivery_phase=completion.delivery_phase,
                provider_failure=completion.failure,
            )
        if not isinstance(completion, OrderPlaced):
            raise TypeError(
                "MedusaStoreClient.complete_cart returned an invalid result"
            )

        completed_order_id = completion.order.id.get_secret_value()
        verified_result = await self.client.get_order(completed_order_id)
        if not isinstance(verified_result, OrderResult):
            raise TypeError("MedusaStoreClient.get_order must return OrderResult")
        recovery_ref = new_opaque_handle()
        recovery_effects = _recovery_effects(
            private_order_id=completed_order_id,
            order_ref=recovery_ref,
            expected_fingerprint=expected_fingerprint,
            contact_form_handle=reviewed_cart.contact_form_handle,
            correlation_id=context.attempt_id,
        )
        if verified_result.failure is not None:
            return _unknown_failure(
                context=context,
                operation_id=PLACE_ORDER.id,
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                provider_failure=verified_result.failure,
                effects=recovery_effects,
            )
        verified_order = verified_result.value
        if verified_order is None:
            raise TypeError("Successful OrderResult is missing its order")
        if (
            verified_order.id.get_secret_value() != completed_order_id
            or not order_matches_fingerprint(
                verified_order,
                expected_fingerprint,
            )
        ):
            return _unknown_failure(
                context=context,
                operation_id=PLACE_ORDER.id,
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                provider_failure=MedusaClientFailure(
                    kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
                    code="order_verification_mismatch",
                    public_message="The completed order could not be verified.",
                ),
                effects=recovery_effects,
            )

        confirmation_handle = new_opaque_handle()
        projection = confirmation_projection(
            verified_order,
            reviewed_cart,
            confirmation_handle=confirmation_handle,
        )
        return OperationOutcome(
            outcome="order_created",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            effects=_confirmation_effects(
                order=verified_order,
                confirmation_handle=confirmation_handle,
                expected_fingerprint=expected_fingerprint,
                contact_form_handle=reviewed_cart.contact_form_handle,
                projection=projection,
            ),
        )


@dataclass(frozen=True)
class ReconcileOrderHandler:
    client: MedusaStoreClient

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        if set(arguments) != {"order_ref"}:
            raise ValueError(f"{RECONCILE_ORDER.id} requires one order_ref")
        order_ref = arguments.get("order_ref")
        if not isinstance(order_ref, str) or not order_ref:
            raise ValueError("order_ref must be a non-empty string")
        provider_values = context.provider_values.to_dict().get(ORDER_PROVIDER.id)
        if not isinstance(provider_values, dict):
            raise RuntimeError("order reconciliation requires typed recovery facts")
        recovery = OrderRecoveryContext.from_provider_values(provider_values)
        if recovery.order_ref != order_ref:
            raise RuntimeError("order recovery facts do not match the request")
        private_order_id = context.private_entity_id("order_ref")

        result = await self.client.get_order(private_order_id)
        if not isinstance(result, OrderResult):
            raise TypeError("MedusaStoreClient.get_order must return OrderResult")
        if result.failure is not None:
            return _client_failure(
                context=context,
                operation_id=RECONCILE_ORDER.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        order = result.value
        if order is None:
            raise TypeError("Successful OrderResult is missing its order")
        if (
            order.id.get_secret_value() != private_order_id
            or not order_matches_fingerprint(
                order,
                recovery.verification_fingerprint,
            )
        ):
            return _client_failure(
                context=context,
                operation_id=RECONCILE_ORDER.id,
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=MedusaClientFailure(
                    kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
                    code="order_verification_mismatch",
                    public_message="The completed order could not be verified.",
                ),
            )
        projection = confirmation_projection_from_order(
            order,
            confirmation_handle=order_ref,
        )
        return OperationOutcome(
            outcome="verified",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            effects=_confirmation_effects(
                order=order,
                confirmation_handle=order_ref,
                expected_fingerprint=recovery.verification_fingerprint,
                contact_form_handle=recovery.contact_form_handle,
                projection=projection,
            ),
        )


class OrdersContinueShoppingHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        if arguments:
            raise ValueError(f"{CONTINUE_SHOPPING.id} accepts no arguments")
        raw = context.provider_values.to_dict().get(CATALOG_PRODUCTS_PROVIDER.id)
        if not isinstance(raw, dict):
            raise RuntimeError("continue shopping requires the authoritative catalog")
        catalog = CatalogCollectionProviderValue.model_validate(raw)
        observation = catalog.observation.model_dump(mode="json", exclude_none=True)
        cards = {
            product.interaction_handle: product
            for product in catalog.observation.products
        }
        product_bindings = tuple(
            EntityBindingEffect(
                public=PublicEntityHandle(
                    entity_kind="product",
                    handle=binding.interaction_handle,
                    values=(
                        PublicValue(
                            name="product_handle",
                            value=FrozenJson(
                                cards[binding.interaction_handle].product_handle
                            ),
                        ),
                        PublicValue(
                            name="title",
                            value=FrozenJson(cards[binding.interaction_handle].title),
                        ),
                    ),
                ),
                private_id=binding.private_id,
                allowed_operation_ids=(OPEN_PRODUCT.id,),
            )
            for binding in catalog.bindings
        )
        return OperationOutcome(
            outcome="continued",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            observation=FrozenJsonObject(observation),
            effects=SessionEffects(
                replace_entities=(
                    EntityKindEffects(entity_kind="order"),
                    EntityKindEffects(entity_kind="cart"),
                    EntityKindEffects(entity_kind="line_item"),
                    EntityKindEffects(entity_kind="shipping_option"),
                    EntityKindEffects(entity_kind="payment_provider"),
                    EntityKindEffects(
                        entity_kind="product",
                        bindings=product_bindings,
                    ),
                ),
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=PRODUCT_GRID.id,
                        values=_public_values(observation),
                    ),
                ),
            ),
        )


def _reviewed_cart(context: ExecutionContext):
    values = context.provider_values.to_dict().get(CHECKOUT_FACTS_PROVIDER.id)
    if not isinstance(values, dict):
        raise RuntimeError("place order requires authoritative checkout facts")
    facts = CheckoutFactsContext.from_provider_values(values)
    if facts.state is not CheckoutFactsState.READY or facts.cart is None:
        raise RuntimeError("place order requires a ready checkout cart")
    return facts.cart


def _recovery_effects(
    *,
    private_order_id: str,
    order_ref: str,
    expected_fingerprint: str,
    contact_form_handle: str,
    correlation_id: str,
) -> SessionEffects:
    recovery_values = {
        "state": "external_outcome_unknown",
        "message": "The order was submitted but its confirmation must be verified.",
        "correlation_id": correlation_id,
        "order_ref": order_ref,
    }
    return SessionEffects(
        replace_entities=(
            EntityKindEffects(
                entity_kind="order",
                bindings=(
                    EntityBindingEffect(
                        public=PublicEntityHandle(
                            entity_kind="order",
                            handle=order_ref,
                            values=(
                                PublicValue(
                                    name="verification_fingerprint",
                                    value=FrozenJson(expected_fingerprint),
                                ),
                                PublicValue(
                                    name="contact_form_handle",
                                    value=FrozenJson(contact_form_handle),
                                ),
                            ),
                        ),
                        private_id=SecretStr(private_order_id),
                        allowed_operation_ids=(RECONCILE_ORDER.id,),
                    ),
                ),
            ),
        ),
        surface_updates=(
            PublicSurfaceEffect(
                surface_id=CHECKOUT_RECOVERY.id,
                values=_public_values(recovery_values),
            ),
        ),
    )


def _confirmation_effects(
    *,
    order: Order,
    confirmation_handle: str,
    expected_fingerprint: str,
    contact_form_handle: str,
    projection: OrderConfirmationProjection,
) -> SessionEffects:
    return SessionEffects(
        replace_entities=(
            EntityKindEffects(entity_kind="cart"),
            EntityKindEffects(entity_kind="line_item"),
            EntityKindEffects(entity_kind="shipping_option"),
            EntityKindEffects(entity_kind="payment_provider"),
            EntityKindEffects(
                entity_kind="order",
                bindings=(
                    EntityBindingEffect(
                        public=PublicEntityHandle(
                            entity_kind="order",
                            handle=confirmation_handle,
                            values=(
                                PublicValue(
                                    name="verification_fingerprint",
                                    value=FrozenJson(expected_fingerprint),
                                ),
                            ),
                        ),
                        private_id=SecretStr(order.id.get_secret_value()),
                    ),
                ),
            ),
        ),
        surface_updates=(
            PublicSurfaceEffect(
                surface_id=ORDER_CONFIRMATION.id,
                values=_public_values(
                    projection.model_dump(mode="json", exclude_none=True)
                ),
            ),
        ),
        remove_private_form_ids=(contact_form_handle,),
        route_params=(
            ExactRouteParameter(
                name="confirmation_handle",
                value=confirmation_handle,
            ),
        ),
        complete_session=True,
    )


def _business_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    code: str,
    message: str,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        failure=RouteDeckFailure(
            kind=FailureKind.BUSINESS,
            code=code,
            phase="complete_cart",
            correlation_id=context.attempt_id,
            operation_id=operation_id,
            request_id=context.request_id,
            public_message=message,
            safe_details=FailureSafeDetails(
                provider="medusa",
                provider_code=code,
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED.value,
            ),
        ),
    )


def _unknown_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    delivery_phase: DeliveryPhase,
    provider_failure: MedusaClientFailure,
    effects: SessionEffects | None = None,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=delivery_phase,
        effects=effects or SessionEffects(),
        failure=RouteDeckFailure(
            kind=FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
            code=provider_failure.code,
            phase="order_verification",
            correlation_id=context.attempt_id,
            operation_id=operation_id,
            request_id=context.request_id,
            public_message="The external outcome is uncertain; do not submit again.",
            safe_details=FailureSafeDetails(
                provider="medusa",
                provider_code=provider_failure.code,
                delivery_phase=delivery_phase.value,
            ),
        ),
    )


def _client_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    delivery_phase: DeliveryPhase,
    failure: MedusaClientFailure,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=delivery_phase,
        failure=RouteDeckFailure(
            kind=_FAILURE_KINDS[failure.kind],
            code=failure.code,
            phase="order_reconciliation",
            correlation_id=context.attempt_id,
            operation_id=operation_id,
            request_id=context.request_id,
            public_message=failure.public_message,
            safe_details=FailureSafeDetails(
                provider="medusa",
                provider_code=failure.code,
                delivery_phase=delivery_phase.value,
            ),
        ),
    )


def _public_values(values: Mapping[str, Any]) -> tuple[PublicValue, ...]:
    return tuple(
        PublicValue(name=name, value=FrozenJson(value))
        for name, value in values.items()
    )


__all__ = [
    "OrdersContinueShoppingHandler",
    "PlaceOrderHandler",
    "ReconcileOrderHandler",
]
