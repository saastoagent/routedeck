from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import SecretStr

from medusa_agent.features.checkout.feature import CHECKOUT_FACTS_PROVIDER
from medusa_agent.features.checkout.handlers import (
    SaveContactHandler,
    StartCheckoutHandler,
)
from medusa_agent.features.checkout.models import (
    BillingChoice,
    CheckoutCartFacts,
    CheckoutFactsContext,
    CheckoutFactsState,
    CheckoutLineFacts,
    ContactAddress,
    LoadedContactDraft,
    PrivateContactDraft,
)
from medusa_agent.medusa.client.models import (
    Cart,
    CartLineItem,
    CartResult,
    StoreAddress,
)
from routedeck_core.contracts.operations import DeliveryPhase, OperationSource
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.ports.executor import ExecutionContext


@pytest.mark.asyncio
async def test_checkout_start_projects_named_buyer_market_defaults() -> None:
    outcome = await StartCheckoutHandler(buyer_country_code="gb")(
        {},
        _execution_context(),
    )

    assert outcome.observation.to_dict() == {
        "form_handle": outcome.observation.to_dict()["form_handle"],
        "revision": 0,
        "complete": False,
        "fields": [
            "email",
            "shipping_address",
            "billing_choice",
            "billing_address",
        ],
        "billing_choices": ["same_as_shipping", "separate"],
        "default_billing_choice": "same_as_shipping",
        "country_choices": ["gb"],
        "default_country_code": "gb",
    }


@pytest.mark.asyncio
async def test_save_contact_rejects_country_outside_injected_buyer_market() -> None:
    contact = PrivateContactDraft(
        email="buyer@example.com",
        shipping_address=_address(country_code="us"),
        billing_choice=BillingChoice.SAME_AS_SHIPPING,
    )
    client = _UnexpectedContactClient()
    handler = SaveContactHandler(
        client,  # type: ignore[arg-type]
        _PrivateContactReader(contact),  # type: ignore[arg-type]
        buyer_country_code="gb",
    )

    outcome = await handler(
        {"form_handle": "private-form-1"},
        _execution_context(),
    )

    assert outcome.outcome is None
    assert outcome.failure is not None
    assert outcome.failure.code == "contact_country_not_allowed"
    assert client.calls == []


@pytest.mark.asyncio
async def test_save_contact_propagates_unexpected_shipping_adapter_type_error() -> None:
    contact = PrivateContactDraft(
        email="buyer@example.com",
        shipping_address=_address(country_code="gb"),
        billing_choice=BillingChoice.SAME_AS_SHIPPING,
    )
    handler = SaveContactHandler(
        _ContactThenBrokenShippingClient(),  # type: ignore[arg-type]
        _PrivateContactReader(contact),  # type: ignore[arg-type]
        buyer_country_code="gb",
    )

    with pytest.raises(TypeError, match="shipping adapter contract bug"):
        await handler(
            {"form_handle": "private-form-1"},
            _execution_context(),
        )


def test_contact_email_uses_standard_validation_and_phone_is_opaque() -> None:
    contact = PrivateContactDraft(
        email="üñîçøðé@example.com",
        shipping_address=_address(country_code="gb", phone="ext 7"),
        billing_choice=BillingChoice.SAME_AS_SHIPPING,
    )

    assert str(contact.email) == "üñîçøðé@example.com"
    assert contact.shipping_address.phone == "ext 7"


def _execution_context() -> ExecutionContext:
    facts = CheckoutFactsContext(
        state=CheckoutFactsState.READY,
        cart=CheckoutCartFacts(
            private_cart_id="private-cart-1",
            private_region_id="private-region-1",
            public_cart_handle="public-cart-1",
            currency_code="gbp",
            items=(
                CheckoutLineFacts(
                    private_variant_id="private-variant-1",
                    title="Linen shirt",
                    quantity=1,
                    unit_amount=4900,
                    total=4900,
                ),
            ),
            item_count=1,
            subtotal=4900,
            shipping_total=0,
            tax_total=0,
            discount_total=0,
            total=4900,
            contact_saved=False,
            billing_complete=False,
            contact_fingerprint="0" * 64,
            shipping_selected=False,
        ),
    )
    return ExecutionContext(
        session_id="session-1",
        request_id="request-1",
        attempt_id="attempt-1",
        node_id="cart.summary",
        source=OperationSource.SURFACE,
        context_fingerprint="context-1",
        provider_values=FrozenJsonObject(
            {CHECKOUT_FACTS_PROVIDER.id: facts.to_provider_values()}
        ),
    )


def _address(*, country_code: str, phone: str | None = None) -> ContactAddress:
    return ContactAddress(
        first_name="Buyer",
        last_name="Example",
        address_1="1 Buyer Street",
        postal_code="SW1A 1AA",
        city="London",
        country_code=country_code,
        phone=phone,
    )


@dataclass
class _PrivateContactReader:
    contact: PrivateContactDraft

    async def load_contact(
        self,
        session_id: str,
        form_handle: str,
    ) -> LoadedContactDraft:
        assert session_id == "session-1"
        assert form_handle == "private-form-1"
        return LoadedContactDraft(
            form_handle=form_handle,
            revision=1,
            contact=self.contact,
        )


@dataclass
class _UnexpectedContactClient:
    calls: list[str] = field(default_factory=list)

    async def set_checkout_contact(self, *_args, **_kwargs):
        self.calls.append("set_checkout_contact")
        raise AssertionError("invalid buyer country must not reach Medusa")


@dataclass
class _ContactThenBrokenShippingClient:
    async def set_checkout_contact(self, *_args, **_kwargs) -> CartResult:
        address = StoreAddress(
            first_name="Buyer",
            last_name="Example",
            address_1="1 Buyer Street",
            postal_code="SW1A 1AA",
            city="London",
            country_code="gb",
        )
        return CartResult(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            value=Cart(
                id=SecretStr("private-cart-1"),
                currency_code="gbp",
                region_id=SecretStr("private-region-1"),
                email="buyer@example.com",
                item_subtotal=4900,
                subtotal=4900,
                total=4900,
                items=(
                    CartLineItem(
                        id=SecretStr("private-line-1"),
                        variant_id=SecretStr("private-variant-1"),
                        title="Linen shirt",
                        quantity=1,
                        unit_price=4900,
                        total=4900,
                    ),
                ),
                shipping_address=address,
                billing_address=address,
            ),
        )

    async def list_shipping_options(self, _cart_id: str):
        raise TypeError("shipping adapter contract bug")
