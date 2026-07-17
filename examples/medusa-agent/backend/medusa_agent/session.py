from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from routedeck_core.app import CompiledApplication
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationRequest,
    OperationSource,
)
from routedeck_core.contracts.projection import FrozenJson
from routedeck_core.contracts.session import (
    PrivateConfiguration,
    PrivateFieldValue,
    PrivateSessionState,
    RouteDeckSession,
    SessionSnapshot,
)
from routedeck_core.runtime import RouteDeckRuntimeServices
from routedeck_core.state.session import create_session

from .features.cart.declarations import CART_CREATE
from .identifiers import MedusaOutcomeType
from .request_ids import initial_cart_request_id


class BuyerMarket(BaseModel):
    """Injected Medusa market identity for one guest buyer session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region_handle: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=2)
    currency_code: str = Field(min_length=3, max_length=3)
    sales_channel_handle: str = Field(min_length=1)


def create_medusa_session(
    *,
    app: CompiledApplication,
    session_id: str,
    market: BuyerMarket,
) -> RouteDeckSession:
    """Create the canonical RouteDeck state for the compiled Medusa graph."""

    private_market = PrivateConfiguration(
        namespace="medusa.buyer_market",
        fields=(
            PrivateFieldValue(
                name="region_handle",
                value=FrozenJson(market.region_handle),
            ),
            PrivateFieldValue(
                name="country_code",
                value=FrozenJson(market.country_code),
            ),
            PrivateFieldValue(
                name="currency_code",
                value=FrozenJson(market.currency_code),
            ),
            PrivateFieldValue(
                name="sales_channel_handle",
                value=FrozenJson(market.sales_channel_handle),
            ),
        ),
    )
    return create_session(
        app=app,
        session_id=session_id,
        private_state=PrivateSessionState(configurations=(private_market,)),
    )


async def initialize_medusa_session(
    services: RouteDeckRuntimeServices,
    created: SessionSnapshot,
) -> SessionSnapshot:
    """Journal the one real cart creation required for a new buyer session."""

    result = await services.runner.run(
        OperationRequest(
            session_id=created.session_id,
            request_id=initial_cart_request_id(created.session_id),
            expected_session_version=created.session_version,
            operation_id=CART_CREATE.id,
            source=OperationSource.SYSTEM,
        )
    )
    if (
        result.disposition is not OperationDisposition.COMPLETED
        or result.outcome != MedusaOutcomeType.CREATED
    ):
        raise RuntimeError(
            "Medusa session initialization did not prove cart creation."
        )
    return await services.store.load(created.session_id)


__all__ = [
    "BuyerMarket",
    "create_medusa_session",
    "initialize_medusa_session",
]
