from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.ports.executor import ExecutionContext

from ....medusa.client.models import (
    MedusaClientFailure,
    MedusaClientFailureKind,
    OrderResult,
)
from ....medusa.client.protocol import MedusaStoreClient
from ..feature import ORDER_PROVIDER, RECONCILE_ORDER
from ..models import (
    OrderRecoveryContext,
    confirmation_projection_from_order,
    order_matches_fingerprint,
)
from .common import client_failure, confirmation_effects


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
            return client_failure(
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
            return client_failure(
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
            effects=confirmation_effects(
                order=order,
                confirmation_handle=order_ref,
                expected_fingerprint=recovery.verification_fingerprint,
                contact_form_handle=recovery.contact_form_handle,
                projection=projection,
            ),
        )
