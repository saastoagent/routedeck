from __future__ import annotations

from routedeck_core.app import FeatureBindings

from ...medusa.client.protocol import MedusaStoreClient
from ..catalog.declarations import CONTINUE_SHOPPING
from ..checkout.declarations import PLACE_ORDER
from .declarations import ORDER_PROVIDER, RECONCILE_ORDER
from .handlers import (
    OrdersContinueShoppingHandler,
    PlaceOrderHandler,
    ReconcileOrderHandler,
)
from .providers import BoundOrderProvider


def create_order_bindings(
    *,
    client: MedusaStoreClient,
    configured_payment_provider_id: str,
) -> FeatureBindings:
    """Bind order placement, recovery, confirmation, and journey reset."""

    return FeatureBindings(
        handlers={
            PLACE_ORDER.ref: PlaceOrderHandler(
                client,
                configured_payment_provider_id,
            ),
            RECONCILE_ORDER.ref: ReconcileOrderHandler(client),
            CONTINUE_SHOPPING.ref: OrdersContinueShoppingHandler(),
        },
        providers={ORDER_PROVIDER.ref: BoundOrderProvider()},
        guards={},
    )


__all__ = ["create_order_bindings"]
