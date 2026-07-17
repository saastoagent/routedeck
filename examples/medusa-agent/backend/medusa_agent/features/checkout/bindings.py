from __future__ import annotations

from routedeck_core.app import FeatureBindings

from ...medusa.client.protocol import MedusaStoreClient
from .declarations import (
    CHECKOUT_FACTS_PROVIDER,
    CHECKOUT_READY_GUARD,
    CHECKOUT_START,
    CONTACT_VALID_GUARD,
    PAYMENT_PROVIDERS_PROVIDER,
    PAYMENT_VALID_GUARD,
    REVIEW_CURRENT_GUARD,
    SAVE_CONTACT,
    SELECT_PAYMENT,
    SELECT_SHIPPING,
    SHIPPING_OPTIONS_PROVIDER,
    SHIPPING_VALID_GUARD,
)
from .guards import (
    CheckoutReadyGuard,
    ContactValidGuard,
    PaymentValidGuard,
    ReviewCurrentGuard,
    ShippingValidGuard,
)
from .operations import (
    SaveContactHandler,
    SelectPaymentHandler,
    SelectShippingHandler,
    StartCheckoutHandler,
)
from .providers import (
    CheckoutFactsProvider,
    CheckoutPrivateFormReader,
    PaymentProvidersProvider,
    ShippingOptionsProvider,
)


def create_checkout_bindings(
    *,
    client: MedusaStoreClient,
    private_forms: CheckoutPrivateFormReader,
    configured_payment_provider_id: str,
    buyer_country_code: str,
) -> FeatureBindings:
    """Bind checkout collection and validation to explicit dependencies."""

    return FeatureBindings(
        handlers={
            CHECKOUT_START.ref: StartCheckoutHandler(
                buyer_country_code=buyer_country_code
            ),
            SAVE_CONTACT.ref: SaveContactHandler(
                client,
                private_forms,
                buyer_country_code=buyer_country_code,
            ),
            SELECT_SHIPPING.ref: SelectShippingHandler(
                client,
                configured_payment_provider_id,
            ),
            SELECT_PAYMENT.ref: SelectPaymentHandler(
                client,
                configured_payment_provider_id,
            ),
        },
        providers={
            CHECKOUT_FACTS_PROVIDER.ref: CheckoutFactsProvider(client),
            SHIPPING_OPTIONS_PROVIDER.ref: ShippingOptionsProvider(client),
            PAYMENT_PROVIDERS_PROVIDER.ref: PaymentProvidersProvider(
                client,
                configured_payment_provider_id,
            ),
        },
        guards={
            CHECKOUT_READY_GUARD.ref: CheckoutReadyGuard(),
            CONTACT_VALID_GUARD.ref: ContactValidGuard(),
            SHIPPING_VALID_GUARD.ref: ShippingValidGuard(),
            PAYMENT_VALID_GUARD.ref: PaymentValidGuard(
                configured_payment_provider_id
            ),
            REVIEW_CURRENT_GUARD.ref: ReviewCurrentGuard(
                configured_payment_provider_id
            ),
        },
    )


__all__ = ["create_checkout_bindings"]
