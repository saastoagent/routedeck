from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
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
    CartResult,
    MedusaClientFailure,
    MedusaClientFailureKind,
)
from ...medusa.client.protocol import MedusaStoreClient
from .feature import (
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_START,
    CONTACT_FORM,
    ORDER_REVIEW,
    PAYMENT_METHOD,
    PAYMENT_PROVIDERS_PROVIDER,
    SAVE_CONTACT,
    SELECT_PAYMENT,
    SELECT_SHIPPING,
    SHIPPING_OPTIONS,
    SHIPPING_OPTIONS_PROVIDER,
)
from .models import (
    BillingChoice,
    CheckoutFactsContext,
    CheckoutFactsState,
    CONTACT_FIELD_NAMES,
    DEFAULT_BILLING_CHOICE,
    EntityHandleFactory,
    PrivateContactDraft,
    PaymentProviderBinding,
    PaymentProviderContext,
    PaymentProviderProjection,
    PaymentProviderState,
    ShippingOptionBinding,
    ShippingOptionProjection,
    ShippingOptionsContext,
    ShippingProviderState,
    order_review_projection,
    project_checkout_cart,
    validate_country_code,
)
from .providers import (
    CheckoutPrivateFormReader,
    PrivateContactDraftError,
    load_payment_provider,
    load_shipping_options,
)


_FAILURE_KINDS = {
    MedusaClientFailureKind.TRANSPORT: FailureKind.TRANSPORT,
    MedusaClientFailureKind.PROVIDER_PROTOCOL: FailureKind.PROVIDER_PROTOCOL,
    MedusaClientFailureKind.BUSINESS: FailureKind.BUSINESS,
}


@dataclass(frozen=True)
class StartCheckoutHandler:
    buyer_country_code: str
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    def __post_init__(self) -> None:
        validate_country_code(self.buyer_country_code)

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        _require_arguments(arguments, expected=(), operation_id=CHECKOUT_START.id)
        _current_cart(context)
        form_values = {
            "form_handle": self.new_entity_handle(),
            "revision": 0,
            "complete": False,
            "fields": list(CONTACT_FIELD_NAMES),
            "billing_choices": [choice.value for choice in BillingChoice],
            "default_billing_choice": DEFAULT_BILLING_CHOICE.value,
            "country_choices": [self.buyer_country_code],
            "default_country_code": self.buyer_country_code,
        }
        return OperationOutcome(
            outcome="started",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            observation=FrozenJsonObject(form_values),
            effects=SessionEffects(
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=CONTACT_FORM.id,
                        values=_public_values(form_values),
                    ),
                )
            ),
        )


@dataclass(frozen=True)
class SaveContactHandler:
    client: MedusaStoreClient
    private_forms: CheckoutPrivateFormReader
    buyer_country_code: str
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    def __post_init__(self) -> None:
        validate_country_code(self.buyer_country_code)

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        _require_arguments(
            arguments,
            expected=("form_handle",),
            operation_id=SAVE_CONTACT.id,
        )
        form_handle = _required_string(arguments, "form_handle")
        current = _current_cart(context)
        try:
            draft = await self.private_forms.load_contact(
                context.session_id,
                form_handle,
            )
        except PrivateContactDraftError as error:
            return _private_form_failure(context, error)

        country_failure = _contact_country_failure(
            draft.contact,
            self.buyer_country_code,
        )
        if country_failure is not None:
            return _private_form_failure(context, country_failure)

        result = await self.client.set_checkout_contact(
            current.private_cart_id,
            draft.contact.to_medusa(),
        )
        if not isinstance(result, CartResult):
            raise TypeError(
                "MedusaStoreClient.set_checkout_contact must return CartResult"
            )
        if result.failure is not None:
            return _failure_outcome(
                context=context,
                operation_id=SAVE_CONTACT.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        cart = result.value
        if cart is None:
            raise TypeError("Successful CartResult is missing its cart")
        if cart.id.get_secret_value() != current.private_cart_id:
            return _protocol_failure_outcome(
                context=context,
                operation_id=SAVE_CONTACT.id,
                code="cart_identity_mismatch",
                message="The store returned a different checkout cart.",
            )
        refreshed = project_checkout_cart(
            cart,
            public_cart_handle=current.public_cart_handle,
            contact_form_handle=draft.form_handle,
        )
        if not refreshed.contact_saved:
            return _protocol_failure_outcome(
                context=context,
                operation_id=SAVE_CONTACT.id,
                code="contact_not_saved",
                message="The store did not confirm the contact details.",
            )

        shipping = await load_shipping_options(
            self.client,
            current.private_cart_id,
            new_entity_handle=self.new_entity_handle,
        )

        observation = {
            "form_handle": draft.form_handle,
            "revision": draft.revision,
            "contact_saved": True,
            "shipping_state": shipping.state.value,
            "shipping_option_count": len(shipping.projection.options),
        }
        return OperationOutcome(
            outcome="saved",
            delivery_phase=result.delivery_phase,
            observation=FrozenJsonObject(observation),
            effects=_shipping_effects(shipping, allow_selection=True),
        )


@dataclass(frozen=True)
class SelectShippingHandler:
    client: MedusaStoreClient
    configured_provider_id: str
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    def __post_init__(self) -> None:
        if not self.configured_provider_id:
            raise ValueError("configured payment provider ID must be non-empty")

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        _require_arguments(
            arguments,
            expected=("shipping_option_ref",),
            operation_id=SELECT_SHIPPING.id,
        )
        selected_ref = _required_string(arguments, "shipping_option_ref")
        current = _current_cart(context)
        shipping = _current_shipping(context)
        private_option_id = context.private_entity_id("shipping_option_ref")
        binding = next(
            item for item in shipping.bindings if item.private_id == private_option_id
        )
        if binding.public_handle != selected_ref:
            raise RuntimeError(
                "resolved shipping option does not match its public handle"
            )
        projected = next(
            item
            for item in shipping.projection.options
            if item.shipping_option_ref == selected_ref
        )

        result = await self.client.set_shipping_option(
            current.private_cart_id,
            private_option_id,
        )
        if not isinstance(result, CartResult):
            raise TypeError(
                "MedusaStoreClient.set_shipping_option must return CartResult"
            )
        if result.failure is not None:
            return _failure_outcome(
                context=context,
                operation_id=SELECT_SHIPPING.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        cart = result.value
        if cart is None:
            raise TypeError("Successful CartResult is missing its cart")
        if cart.id.get_secret_value() != current.private_cart_id:
            return _protocol_failure_outcome(
                context=context,
                operation_id=SELECT_SHIPPING.id,
                code="cart_identity_mismatch",
                message="The store returned a different checkout cart.",
            )
        selected_ids = {
            method.shipping_option_id.get_secret_value()
            for method in cart.shipping_methods
        }
        if private_option_id not in selected_ids:
            return _protocol_failure_outcome(
                context=context,
                operation_id=SELECT_SHIPPING.id,
                code="shipping_not_selected",
                message="The store did not confirm the delivery selection.",
            )

        payment = await load_payment_provider(
            self.client,
            cart.region_id.get_secret_value(),
            self.configured_provider_id,
            new_entity_handle=self.new_entity_handle,
        )

        observation = projected.model_dump(mode="json")
        return OperationOutcome(
            outcome="selected",
            delivery_phase=result.delivery_phase,
            observation=FrozenJsonObject(observation),
            effects=SessionEffects(
                replace_entities=(
                    EntityKindEffects(
                        entity_kind="shipping_option",
                        bindings=(
                            _shipping_binding_effect(
                                binding,
                                projected,
                                allowed_operation_ids=(),
                            ),
                        ),
                    ),
                    EntityKindEffects(
                        entity_kind="payment_provider",
                        bindings=_payment_binding_effects(
                            payment,
                            allowed_operation_ids=(SELECT_PAYMENT.id,),
                        ),
                    ),
                ),
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=PAYMENT_METHOD.id,
                        values=_public_values(
                            payment.projection.model_dump(
                                mode="json", exclude_none=True
                            )
                        ),
                    ),
                ),
            ),
        )


@dataclass(frozen=True)
class SelectPaymentHandler:
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
        _require_arguments(
            arguments,
            expected=("payment_provider_ref",),
            operation_id=SELECT_PAYMENT.id,
        )
        selected_ref = _required_string(arguments, "payment_provider_ref")
        current = _current_cart(context)
        payment = _current_payment(context)
        private_provider_id = context.private_entity_id("payment_provider_ref")
        if private_provider_id != self.configured_provider_id:
            raise RuntimeError(
                "resolved payment provider is not the configured provider"
            )
        binding = payment.bindings[0]
        projection = payment.projection.providers[0]
        if (
            binding.public_handle != selected_ref
            or binding.private_id != private_provider_id
            or projection.payment_provider_ref != selected_ref
        ):
            raise RuntimeError(
                "resolved payment provider does not match its projection"
            )

        cart_result = await self.client.get_cart(current.private_cart_id)
        if not isinstance(cart_result, CartResult):
            raise TypeError("MedusaStoreClient.get_cart must return CartResult")
        if cart_result.failure is not None:
            return _failure_outcome(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                delivery_phase=DeliveryPhase.NOT_SENT,
                failure=cart_result.failure,
            )
        cart = cart_result.value
        if cart is None:
            raise TypeError("Successful CartResult is missing its cart")
        if cart.id.get_secret_value() != current.private_cart_id:
            return _prewrite_business_failure(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                code="cart_identity_mismatch",
                message="The checkout cart changed before payment selection.",
            )
        refreshed_before_write = project_checkout_cart(
            cart,
            public_cart_handle=current.public_cart_handle,
            contact_form_handle=current.contact_form_handle,
        )
        if refreshed_before_write != current:
            return _prewrite_business_failure(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                code="checkout_changed",
                message="The checkout changed. Review the latest totals and try again.",
            )

        result = await self.client.initialize_payment(
            cart,
            self.configured_provider_id,
        )
        if not isinstance(result, CartResult):
            raise TypeError(
                "MedusaStoreClient.initialize_payment must return CartResult"
            )
        if result.failure is not None:
            return _failure_outcome(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        initialized = result.value
        if initialized is None:
            raise TypeError("Successful CartResult is missing its cart")
        if initialized.id.get_secret_value() != current.private_cart_id:
            return _protocol_failure_outcome(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                code="cart_identity_mismatch",
                message="The store returned a different checkout cart.",
            )
        refreshed = project_checkout_cart(
            initialized,
            public_cart_handle=current.public_cart_handle,
            contact_form_handle=current.contact_form_handle,
        )
        if refreshed.payment_provider_ids != (self.configured_provider_id,):
            return _protocol_failure_outcome(
                context=context,
                operation_id=SELECT_PAYMENT.id,
                code="payment_not_initialized",
                message="The store did not confirm the configured payment method.",
            )
        review = order_review_projection(
            refreshed,
            payment_label=projection.label,
        )
        return OperationOutcome(
            outcome="selected",
            delivery_phase=result.delivery_phase,
            observation=FrozenJsonObject(projection.model_dump(mode="json")),
            effects=SessionEffects(
                replace_entities=(
                    EntityKindEffects(entity_kind="shipping_option"),
                    EntityKindEffects(entity_kind="payment_provider"),
                ),
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=ORDER_REVIEW.id,
                        values=_public_values(review.model_dump(mode="json")),
                    ),
                ),
            ),
        )


def _shipping_effects(
    shipping: ShippingOptionsContext,
    *,
    allow_selection: bool,
) -> SessionEffects:
    projections = {
        option.shipping_option_ref: option for option in shipping.projection.options
    }
    allowed_operation_ids = (SELECT_SHIPPING.id,) if allow_selection else ()
    bindings = tuple(
        _shipping_binding_effect(
            binding,
            projections[binding.public_handle],
            allowed_operation_ids=allowed_operation_ids,
        )
        for binding in shipping.bindings
    )
    surface = shipping.projection.model_dump(mode="json", exclude_none=True)
    return SessionEffects(
        replace_entities=(
            EntityKindEffects(entity_kind="shipping_option", bindings=bindings),
        ),
        surface_updates=(
            PublicSurfaceEffect(
                surface_id=SHIPPING_OPTIONS.id,
                values=_public_values(surface),
            ),
        ),
    )


def _shipping_binding_effect(
    binding: ShippingOptionBinding,
    projection: ShippingOptionProjection,
    *,
    allowed_operation_ids: tuple[str, ...],
) -> EntityBindingEffect:
    if binding.public_handle != projection.shipping_option_ref:
        raise ValueError("shipping projection and binding must match")
    return EntityBindingEffect(
        public=PublicEntityHandle(
            entity_kind="shipping_option",
            handle=binding.public_handle,
            values=tuple(
                PublicValue(name=name, value=FrozenJson(value))
                for name, value in projection.model_dump(mode="json").items()
                if name != "shipping_option_ref"
            ),
        ),
        private_id=SecretStr(binding.private_id),
        allowed_operation_ids=allowed_operation_ids,
    )


def _payment_binding_effects(
    payment: PaymentProviderContext,
    *,
    allowed_operation_ids: tuple[str, ...],
) -> tuple[EntityBindingEffect, ...]:
    if payment.state is not PaymentProviderState.READY:
        return ()
    projections = {
        provider.payment_provider_ref: provider
        for provider in payment.projection.providers
    }
    return tuple(
        _payment_binding_effect(
            binding,
            projections[binding.public_handle],
            allowed_operation_ids=allowed_operation_ids,
        )
        for binding in payment.bindings
    )


def _payment_binding_effect(
    binding: PaymentProviderBinding,
    projection: PaymentProviderProjection,
    *,
    allowed_operation_ids: tuple[str, ...],
) -> EntityBindingEffect:
    if binding.public_handle != projection.payment_provider_ref:
        raise ValueError("payment projection and binding must match")
    return EntityBindingEffect(
        public=PublicEntityHandle(
            entity_kind="payment_provider",
            handle=binding.public_handle,
            values=(PublicValue(name="label", value=FrozenJson(projection.label)),),
        ),
        private_id=SecretStr(binding.private_id),
        allowed_operation_ids=allowed_operation_ids,
    )


def _current_cart(context: ExecutionContext):
    values = context.provider_values.to_dict().get(CHECKOUT_FACTS_PROVIDER.id)
    if not isinstance(values, dict):
        raise RuntimeError("checkout handler requires typed cart facts")
    facts = CheckoutFactsContext.from_provider_values(values)
    if facts.state is not CheckoutFactsState.READY or facts.cart is None:
        raise RuntimeError("checkout handler requires an authoritative cart")
    return facts.cart


def _current_shipping(context: ExecutionContext) -> ShippingOptionsContext:
    values = context.provider_values.to_dict().get(SHIPPING_OPTIONS_PROVIDER.id)
    if not isinstance(values, dict):
        raise RuntimeError("shipping handler requires typed options")
    shipping = ShippingOptionsContext.from_provider_values(values)
    if shipping.state is not ShippingProviderState.READY:
        raise RuntimeError("shipping handler requires current delivery options")
    return shipping


def _current_payment(context: ExecutionContext) -> PaymentProviderContext:
    values = context.provider_values.to_dict().get(PAYMENT_PROVIDERS_PROVIDER.id)
    if not isinstance(values, dict):
        raise RuntimeError("payment handler requires typed provider values")
    payment = PaymentProviderContext.from_provider_values(values)
    if payment.state is not PaymentProviderState.READY:
        raise RuntimeError("payment handler requires the configured payment provider")
    return payment


def _private_form_failure(
    context: ExecutionContext,
    error: PrivateContactDraftError,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=DeliveryPhase.NOT_SENT,
        failure=RouteDeckFailure(
            kind=FailureKind.BUSINESS,
            code=error.code,
            phase="private_form_validation",
            correlation_id=context.attempt_id,
            operation_id=SAVE_CONTACT.id,
            request_id=context.request_id,
            public_message=error.public_message,
            safe_details=FailureSafeDetails(delivery_phase="not_sent"),
        ),
    )


def _contact_country_failure(
    contact: PrivateContactDraft,
    buyer_country_code: str,
) -> PrivateContactDraftError | None:
    addresses = [contact.shipping_address]
    if contact.billing_choice is BillingChoice.SEPARATE:
        if contact.billing_address is None:
            raise RuntimeError("validated separate billing contact has no address")
        addresses.append(contact.billing_address)
    if any(address.country_code != buyer_country_code for address in addresses):
        return PrivateContactDraftError(
            "contact_country_not_allowed",
            "Choose the configured buyer country for shipping and billing.",
        )
    return None


def _failure_outcome(
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
            phase="execute",
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


def _protocol_failure_outcome(
    *,
    context: ExecutionContext,
    operation_id: str,
    code: str,
    message: str,
) -> OperationOutcome:
    return _failure_outcome(
        context=context,
        operation_id=operation_id,
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        failure=MedusaClientFailure(
            kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
            code=code,
            public_message=message,
        ),
    )


def _prewrite_business_failure(
    *,
    context: ExecutionContext,
    operation_id: str,
    code: str,
    message: str,
) -> OperationOutcome:
    return _failure_outcome(
        context=context,
        operation_id=operation_id,
        delivery_phase=DeliveryPhase.NOT_SENT,
        failure=MedusaClientFailure(
            kind=MedusaClientFailureKind.BUSINESS,
            code=code,
            public_message=message,
        ),
    )


def _require_arguments(
    arguments: Mapping[str, Any],
    *,
    expected: tuple[str, ...],
    operation_id: str,
) -> None:
    if set(arguments) != set(expected):
        raise ValueError(
            f"{operation_id} requires exactly these arguments: {expected!r}"
        )


def _required_string(arguments: Mapping[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _public_values(values: Mapping[str, Any]) -> tuple[PublicValue, ...]:
    return tuple(
        PublicValue(name=name, value=FrozenJson(value))
        for name, value in values.items()
    )


__all__ = [
    "SaveContactHandler",
    "SelectPaymentHandler",
    "SelectShippingHandler",
    "StartCheckoutHandler",
]
