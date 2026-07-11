from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from routedeck_core.contracts.projection import FrozenJson, PublicProjection
from routedeck_core.contracts.session import (
    PrivateConfiguration,
    PrivateFieldValue,
    PrivateSessionState,
    RouteDeckSession,
)
from routedeck_core.projection.projector import ProjectionProjector
from routedeck_core.state.session import create_session

from .composition import compile_medusa_app_spec


class BuyerMarket(BaseModel):
    """Injected Medusa market identity for one guest buyer session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    region_handle: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=2)
    currency_code: str = Field(min_length=3, max_length=3)
    sales_channel_handle: str = Field(min_length=1)


def create_medusa_session(
    *,
    session_id: str,
    market: BuyerMarket,
) -> RouteDeckSession:
    """Create the canonical RouteDeck state for the compiled Medusa graph."""

    app = compile_medusa_app_spec()
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


def project_medusa_session(session: RouteDeckSession) -> PublicProjection:
    """Project through the generic framework projector, without product state."""

    return ProjectionProjector(compile_medusa_app_spec()).project(session)


__all__ = ["BuyerMarket", "create_medusa_session", "project_medusa_session"]
