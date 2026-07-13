from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
    SessionEffects,
)
from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.contracts.projection import (
    FrozenJson,
    FrozenJsonObject,
    PublicEntityHandle,
    PublicValue,
)
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ....medusa.client.models import CreateCartRequest, CreateCartResult
from ....medusa.client.protocol import MedusaStoreClient
from ..feature import BUYER_MARKET_PROVIDER, CART_CREATE, CART_CREATED_OUTCOME
from ..models import EntityHandleFactory
from .common import (
    failure_outcome,
    protocol_failure_outcome,
    provider_mapping,
    require_arguments,
    required_string,
)


@dataclass(frozen=True)
class CreateCartHandler:
    """Create exactly one cart through the journaled Store write boundary."""

    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        require_arguments(arguments, expected=(), operation_id=CART_CREATE.id)
        market = provider_mapping(context, BUYER_MARKET_PROVIDER.id)
        request = CreateCartRequest(
            region_id=required_string(market, "region_id"),
            country_code=required_string(market, "country_code"),
            sales_channel_id=required_string(market, "sales_channel_id"),
        )
        result = await self.client.create_cart(request)
        if not isinstance(result, CreateCartResult):
            raise TypeError(
                "MedusaStoreClient.create_cart must return CreateCartResult"
            )
        if result.failure is not None:
            return failure_outcome(
                context=context,
                operation_id=CART_CREATE.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        cart = result.cart
        if cart is None:
            raise TypeError("Successful CreateCartResult is missing its cart")
        expected_currency = required_string(market, "currency_code")
        if cart.currency_code != expected_currency:
            return protocol_failure_outcome(
                context=context,
                operation_id=CART_CREATE.id,
                code="cart_currency_mismatch",
                message="The store created a cart for an unexpected currency.",
            )

        private_cart_id = cart.id.get_secret_value()
        public_cart_handle = self.new_entity_handle()
        effects = SessionEffects(
            replace_entities=(
                EntityKindEffects(
                    entity_kind="cart",
                    bindings=(
                        EntityBindingEffect(
                            public=PublicEntityHandle(
                                entity_kind="cart",
                                handle=public_cart_handle,
                                values=(
                                    PublicValue(
                                        name="currency_code",
                                        value=FrozenJson(cart.currency_code),
                                    ),
                                ),
                            ),
                            private_id=SecretStr(private_cart_id),
                        ),
                    ),
                ),
            ),
        )
        return OperationOutcome(
            outcome=CART_CREATED_OUTCOME,
            delivery_phase=result.delivery_phase,
            observation=FrozenJsonObject(
                {
                    "cart_id": private_cart_id,
                    "currency_code": cart.currency_code,
                }
            ),
            effects=effects,
        )
