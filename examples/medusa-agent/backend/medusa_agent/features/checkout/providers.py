from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import ValidationError

from routedeck_core.contracts.operations import DeliveryPhase
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.session import RouteDeckSession
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports import RouteDeckSessionStore
from routedeck_core.supervision.guards import ProviderInvocationContext, ProviderResult

from ...medusa.client.models import (
    CartResult,
    MedusaClientFailureKind,
    PaymentProvidersResult,
    ShippingOptionsResult,
)
from ...medusa.client.protocol import MedusaStoreClient
from .models import (
    CheckoutFactsContext,
    CheckoutFactsState,
    EntityHandleFactory,
    LoadedContactDraft,
    PaymentMethodProjection,
    PaymentProviderBinding,
    PaymentProviderContext,
    PaymentProviderProjection,
    PaymentProviderState,
    PrivateContactDraft,
    ShippingOptionBinding,
    ShippingOptionProjection,
    ShippingOptionsContext,
    ShippingOptionsProjection,
    ShippingProviderState,
    project_checkout_cart,
)


@runtime_checkable
class PrivateFormCodec(Protocol):
    def decrypt(self, value: bytes) -> bytes: ...


@runtime_checkable
class CheckoutPrivateFormReader(Protocol):
    async def load_contact(
        self,
        session_id: str,
        form_handle: str,
    ) -> LoadedContactDraft: ...


class PrivateContactDraftError(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.public_message = public_message


@dataclass(frozen=True)
class EncryptedCheckoutPrivateFormReader:
    """Load and validate one contact draft without exposing its plaintext."""

    store: RouteDeckSessionStore
    codec: PrivateFormCodec

    async def load_contact(
        self,
        session_id: str,
        form_handle: str,
    ) -> LoadedContactDraft:
        if not form_handle:
            raise PrivateContactDraftError(
                "private_form_required",
                "Complete the contact form before continuing.",
            )
        try:
            snapshot = await self.store.load(session_id)
        except Exception:
            raise PrivateContactDraftError(
                "private_form_unavailable",
                "The contact form could not be loaded.",
            ) from None
        drafts = tuple(
            draft
            for draft in snapshot.state.private_state.drafts
            if draft.form_id == form_handle
        )
        if len(drafts) != 1:
            raise PrivateContactDraftError(
                "private_form_not_found",
                "Complete the contact form before continuing.",
            )
        draft = drafts[0]
        if not draft.complete:
            raise PrivateContactDraftError(
                "private_form_incomplete",
                "Complete every required contact field before continuing.",
            )
        try:
            encrypted = await self.store.load_private_blob(session_id, form_handle)
        except Exception:
            raise PrivateContactDraftError(
                "private_form_unavailable",
                "The contact form could not be loaded.",
            ) from None
        if encrypted is None:
            raise PrivateContactDraftError(
                "private_form_state_mismatch",
                "The contact form could not be loaded.",
            )
        try:
            value = json.loads(self.codec.decrypt(encrypted))
        except Exception:
            raise PrivateContactDraftError(
                "private_form_unavailable",
                "The contact form could not be loaded.",
            ) from None
        if not isinstance(value, dict) or any(
            not isinstance(name, str) for name in value
        ):
            raise PrivateContactDraftError(
                "private_form_invalid",
                "The contact form contains invalid fields.",
            )
        if tuple(sorted(value)) != draft.field_names:
            raise PrivateContactDraftError(
                "private_form_state_mismatch",
                "The contact form could not be loaded.",
            )
        if value.get("billing_choice") == "separate" and not isinstance(
            value.get("billing_address"), dict
        ):
            raise PrivateContactDraftError(
                "billing_address_required",
                "Enter a separate billing address before continuing.",
            )
        try:
            contact = PrivateContactDraft.model_validate(value)
        except ValidationError:
            raise PrivateContactDraftError(
                "contact_invalid",
                "Review the contact and address fields before continuing.",
            ) from None
        return LoadedContactDraft(
            form_handle=form_handle,
            revision=draft.revision,
            contact=contact,
        )


@dataclass(frozen=True)
class CheckoutFactsProvider:
    client: MedusaStoreClient

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        cart_binding = _one_cart_binding(context.session)
        if cart_binding is None:
            return _provider_result(
                CheckoutFactsContext(state=CheckoutFactsState.MISSING)
            )
        result = await self.client.get_cart(cart_binding.private_id)
        if not isinstance(result, CartResult):
            raise TypeError("MedusaStoreClient.get_cart must return CartResult")
        if result.failure is not None:
            return _provider_result(
                CheckoutFactsContext(
                    state=CheckoutFactsState.REFRESH_FAILED,
                    delivery_phase=result.delivery_phase,
                    failure_kind=result.failure.kind,
                    failure_code=result.failure.code,
                    public_message=result.failure.public_message,
                )
            )
        cart = result.value
        if cart is None:
            raise TypeError("Successful CartResult is missing its cart")
        if cart.id.get_secret_value() != cart_binding.private_id:
            raise TypeError("Medusa returned a different checkout cart")
        return _provider_result(
            CheckoutFactsContext(
                state=CheckoutFactsState.READY,
                cart=project_checkout_cart(
                    cart,
                    public_cart_handle=cart_binding.public_handle,
                    contact_form_handle=_completed_contact_form_handle(context.session),
                ),
            )
        )


@dataclass(frozen=True)
class ShippingOptionsProvider:
    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        cart_binding = _one_cart_binding(context.session)
        if cart_binding is None:
            result = _shipping_failure(
                delivery_phase=DeliveryPhase.NOT_SENT,
                failure_kind=MedusaClientFailureKind.BUSINESS,
                failure_code="cart_required",
                public_message="A cart is required before delivery can be selected.",
            )
        else:
            existing = {
                binding.private_id: binding.public_handle
                for binding in context.session.private_state.entity_bindings
                if binding.entity_kind == "shipping_option"
            }
            result = await load_shipping_options(
                self.client,
                cart_binding.private_id,
                existing_handles=existing,
                new_entity_handle=self.new_entity_handle,
            )
        return ProviderResult(values=FrozenJsonObject(result.to_provider_values()))


@dataclass(frozen=True)
class PaymentProvidersProvider:
    client: MedusaStoreClient
    configured_provider_id: str
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    def __post_init__(self) -> None:
        if not self.configured_provider_id:
            raise ValueError("configured payment provider ID must be non-empty")

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        cart_binding = _one_cart_binding(context.session)
        if cart_binding is None:
            payment = _payment_missing(
                "A cart is required before payment can be selected."
            )
        else:
            cart_result = await self.client.get_cart(cart_binding.private_id)
            if not isinstance(cart_result, CartResult):
                raise TypeError("MedusaStoreClient.get_cart must return CartResult")
            if cart_result.failure is not None:
                payment = _payment_failure(
                    delivery_phase=cart_result.delivery_phase,
                    failure_kind=cart_result.failure.kind,
                    failure_code=cart_result.failure.code,
                    public_message=cart_result.failure.public_message,
                )
            else:
                cart = cart_result.value
                if cart is None:
                    raise TypeError("Successful CartResult is missing its cart")
                if cart.id.get_secret_value() != cart_binding.private_id:
                    raise TypeError("Medusa returned a different checkout cart")
                existing = {
                    binding.private_id: binding.public_handle
                    for binding in context.session.private_state.entity_bindings
                    if binding.entity_kind == "payment_provider"
                }
                payment = await load_payment_provider(
                    self.client,
                    cart.region_id.get_secret_value(),
                    self.configured_provider_id,
                    existing_handles=existing,
                    new_entity_handle=self.new_entity_handle,
                )
        return ProviderResult(values=FrozenJsonObject(payment.to_provider_values()))


async def load_shipping_options(
    client: MedusaStoreClient,
    private_cart_id: str,
    *,
    existing_handles: dict[str, str] | None = None,
    new_entity_handle: EntityHandleFactory = new_opaque_handle,
) -> ShippingOptionsContext:
    result = await client.list_shipping_options(private_cart_id)
    if not isinstance(result, ShippingOptionsResult):
        raise TypeError(
            "MedusaStoreClient.list_shipping_options must return ShippingOptionsResult"
        )
    if result.failure is not None:
        return _shipping_failure(
            delivery_phase=result.delivery_phase,
            failure_kind=result.failure.kind,
            failure_code=result.failure.code,
            public_message=result.failure.public_message,
        )
    options = result.value
    if options is None:
        raise TypeError("Successful ShippingOptionsResult is missing its options")
    if not options:
        return ShippingOptionsContext(
            state=ShippingProviderState.EMPTY,
            projection=ShippingOptionsProjection(
                state=ShippingProviderState.EMPTY,
                message="No delivery options are available for this address.",
            ),
        )

    existing = dict(existing_handles or {})
    bindings: list[ShippingOptionBinding] = []
    projections: list[ShippingOptionProjection] = []
    seen_ids: set[str] = set()
    for option in options:
        private_id = option.id.get_secret_value()
        if private_id in seen_ids:
            return _shipping_failure(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure_kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
                failure_code="duplicate_shipping_option",
                public_message="The store returned invalid delivery options.",
            )
        seen_ids.add(private_id)
        price = option.calculated_price
        if price is None:
            return _shipping_failure(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure_kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
                failure_code="shipping_price_missing",
                public_message="A delivery option has no authoritative price.",
            )
        public_handle = existing.get(private_id)
        if public_handle is None:
            public_handle = new_entity_handle()
        bindings.append(
            ShippingOptionBinding(
                public_handle=public_handle,
                private_id=private_id,
            )
        )
        projections.append(
            ShippingOptionProjection(
                shipping_option_ref=public_handle,
                label=option.name,
                amount=price.calculated_amount,
                currency_code=price.currency_code,
            )
        )
    return ShippingOptionsContext(
        state=ShippingProviderState.READY,
        projection=ShippingOptionsProjection(
            state=ShippingProviderState.READY,
            options=tuple(projections),
        ),
        bindings=tuple(bindings),
    )


async def load_payment_provider(
    client: MedusaStoreClient,
    private_region_id: str,
    configured_provider_id: str,
    *,
    existing_handles: dict[str, str] | None = None,
    new_entity_handle: EntityHandleFactory = new_opaque_handle,
) -> PaymentProviderContext:
    if not private_region_id or not configured_provider_id:
        raise ValueError("region and configured payment provider IDs are required")
    result = await client.list_payment_providers(private_region_id)
    if not isinstance(result, PaymentProvidersResult):
        raise TypeError(
            "MedusaStoreClient.list_payment_providers must return PaymentProvidersResult"
        )
    if result.failure is not None:
        return _payment_failure(
            delivery_phase=result.delivery_phase,
            failure_kind=result.failure.kind,
            failure_code=result.failure.code,
            public_message=result.failure.public_message,
        )
    providers = result.value
    if providers is None:
        raise TypeError("Successful PaymentProvidersResult is missing its providers")
    matches = tuple(
        provider
        for provider in providers
        if provider.id == configured_provider_id and provider.is_enabled
    )
    if len(matches) > 1:
        return _payment_failure(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            failure_kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
            failure_code="duplicate_payment_provider",
            public_message="The store returned an invalid payment configuration.",
        )
    if not matches:
        return _payment_missing(
            "The configured payment method is unavailable for this checkout."
        )
    existing = dict(existing_handles or {})
    public_handle = existing.get(configured_provider_id) or new_entity_handle()
    projection = PaymentProviderProjection(
        payment_provider_ref=public_handle,
        label="System / manual demo payment",
    )
    return PaymentProviderContext(
        state=PaymentProviderState.READY,
        projection=PaymentMethodProjection(
            state=PaymentProviderState.READY,
            providers=(projection,),
        ),
        bindings=(
            PaymentProviderBinding(
                public_handle=public_handle,
                private_id=configured_provider_id,
            ),
        ),
    )


def _one_cart_binding(session: RouteDeckSession):
    bindings = tuple(
        binding
        for binding in session.private_state.entity_bindings
        if binding.entity_kind == "cart"
    )
    if len(bindings) > 1:
        raise RuntimeError("checkout session contains multiple cart bindings")
    if not bindings:
        return None
    public = tuple(
        entity
        for entity in session.public_state.entity_handles
        if entity.entity_kind == "cart" and entity.handle == bindings[0].public_handle
    )
    if len(public) != 1:
        raise RuntimeError("checkout cart has no exact public binding")
    return bindings[0]


def _completed_contact_form_handle(session: RouteDeckSession) -> str | None:
    allowed_field_sets = {
        ("billing_choice", "email", "shipping_address"),
        ("billing_address", "billing_choice", "email", "shipping_address"),
    }
    matches = tuple(
        draft
        for draft in session.private_state.drafts
        if draft.complete and tuple(sorted(draft.field_names)) in allowed_field_sets
    )
    if len(matches) > 1:
        raise RuntimeError(
            "checkout session contains multiple completed contact drafts"
        )
    return matches[0].form_id if matches else None


def _provider_result(context: CheckoutFactsContext) -> ProviderResult:
    return ProviderResult(values=FrozenJsonObject(context.to_provider_values()))


def _shipping_failure(
    *,
    delivery_phase: DeliveryPhase,
    failure_kind: MedusaClientFailureKind,
    failure_code: str,
    public_message: str,
) -> ShippingOptionsContext:
    return ShippingOptionsContext(
        state=ShippingProviderState.REFRESH_FAILED,
        projection=ShippingOptionsProjection(
            state=ShippingProviderState.REFRESH_FAILED,
            message=public_message,
        ),
        delivery_phase=delivery_phase,
        failure_kind=failure_kind,
        failure_code=failure_code,
    )


def _payment_missing(public_message: str) -> PaymentProviderContext:
    return PaymentProviderContext(
        state=PaymentProviderState.MISSING,
        projection=PaymentMethodProjection(
            state=PaymentProviderState.MISSING,
            message=public_message,
        ),
    )


def _payment_failure(
    *,
    delivery_phase: DeliveryPhase,
    failure_kind: MedusaClientFailureKind,
    failure_code: str,
    public_message: str,
) -> PaymentProviderContext:
    return PaymentProviderContext(
        state=PaymentProviderState.REFRESH_FAILED,
        projection=PaymentMethodProjection(
            state=PaymentProviderState.REFRESH_FAILED,
            message=public_message,
        ),
        delivery_phase=delivery_phase,
        failure_kind=failure_kind,
        failure_code=failure_code,
    )


__all__ = [
    "CheckoutFactsProvider",
    "CheckoutPrivateFormReader",
    "EncryptedCheckoutPrivateFormReader",
    "PrivateContactDraftError",
    "PrivateFormCodec",
    "PaymentProvidersProvider",
    "ShippingOptionsProvider",
    "load_payment_provider",
    "load_shipping_options",
]
