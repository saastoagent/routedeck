from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.effects import PublicSurfaceEffect, SessionEffects
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ..feature import CHECKOUT_START, CONTACT_FORM
from ..models import (
    BillingChoice,
    CONTACT_FIELD_NAMES,
    DEFAULT_BILLING_CHOICE,
    EntityHandleFactory,
    validate_country_code,
)
from .common import public_values, require_current_cart, require_exact_arguments


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
        require_exact_arguments(
            arguments,
            expected=(),
            operation_id=CHECKOUT_START.id,
        )
        require_current_cart(context)
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
                        values=public_values(form_values),
                    ),
                )
            ),
        )


__all__ = ["StartCheckoutHandler"]
