from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ....identifiers import MedusaOutcomeType
from ....medusa.client.models import CartResult
from ....medusa.client.protocol import MedusaStoreClient
from ..feature import SAVE_CONTACT
from ..models import EntityHandleFactory, project_checkout_cart, validate_country_code
from ..providers import (
    CheckoutPrivateFormReader,
    PrivateContactDraftError,
    load_shipping_options,
)
from .common import (
    contact_country_failure,
    operation_failure,
    private_form_failure,
    protocol_failure,
    require_current_cart,
    require_exact_arguments,
    require_string,
)
from .delivery_effects import shipping_effects


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
        require_exact_arguments(
            arguments,
            expected=("form_handle",),
            operation_id=SAVE_CONTACT.id,
        )
        form_handle = require_string(arguments, "form_handle")
        current = require_current_cart(context)
        try:
            draft = await self.private_forms.load_contact(
                context.session_id,
                form_handle,
            )
        except PrivateContactDraftError as error:
            return private_form_failure(context, error)

        country_failure = contact_country_failure(
            draft.contact,
            self.buyer_country_code,
        )
        if country_failure is not None:
            return private_form_failure(context, country_failure)

        result = await self.client.set_checkout_contact(
            current.private_cart_id,
            draft.contact.to_medusa(),
        )
        if not isinstance(result, CartResult):
            raise TypeError(
                "MedusaStoreClient.set_checkout_contact must return CartResult"
            )
        if result.failure is not None:
            return operation_failure(
                context=context,
                operation_id=SAVE_CONTACT.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        cart = result.value
        if cart is None:
            raise TypeError("Successful CartResult is missing its cart")
        if cart.id.get_secret_value() != current.private_cart_id:
            return protocol_failure(
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
            return protocol_failure(
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
            outcome=MedusaOutcomeType.SAVED,
            delivery_phase=result.delivery_phase,
            observation=FrozenJsonObject(observation),
            effects=shipping_effects(shipping, allow_selection=True),
        )


__all__ = ["SaveContactHandler"]
