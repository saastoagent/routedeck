from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import SecretStr

from medusa_agent.config import Settings
from medusa_agent.medusa.client.models import (
    MedusaClientFailure,
    MedusaClientFailureKind,
    Region,
    RegionCountry,
    RegionsResult,
)
from medusa_agent.runtime import LiveMedusaReadiness
from medusa_agent.session import BuyerMarket
from routedeck_core.contracts.operations import DeliveryPhase
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode


@pytest.mark.asyncio
async def test_live_readiness_checks_store_and_configured_medusa_market() -> None:
    runtime = _ReadinessRuntime(
        initial_market=_buyer_market(),
        store_error=SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND),
    )
    client = _RegionsClient(
        RegionsResult.succeeded(
            (
                Region(
                    id=SecretStr("region-1"),
                    name="United Kingdom",
                    currency_code="gbp",
                    countries=(RegionCountry(iso_2="gb"),),
                ),
            )
        )
    )
    readiness = LiveMedusaReadiness(
        runtime=runtime,  # type: ignore[arg-type]
        client=client,  # type: ignore[arg-type]
        settings=_settings(),
    )

    assert await readiness.routedeck_store_ready() is True
    assert await readiness.medusa_ready() is True
    assert client.calls == 1

    runtime.store_error = SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
    client.result = RegionsResult.failed(
        delivery_phase=DeliveryPhase.NOT_SENT,
        failure=MedusaClientFailure(
            kind=MedusaClientFailureKind.TRANSPORT,
            code="medusa_unavailable",
            public_message="The store is unavailable.",
        ),
    )

    assert await readiness.routedeck_store_ready() is False
    assert await readiness.medusa_ready() is False


def _settings() -> Settings:
    return Settings(
        medusa_base_url="http://medusa.test",
        medusa_publishable_key=SecretStr("publishable-key"),
        medusa_region_id="region-1",
        medusa_country_code="gb",
        medusa_sales_channel_id="channel-1",
        medusa_payment_provider_id="pp_system_default",
        routedeck_database_path=Path("routedeck.sqlite"),
        routedeck_state_encryption_key=SecretStr("encryption-key"),
        openai_api_key=SecretStr("openai-key"),
        openai_model="model-1",
    )


def _buyer_market() -> BuyerMarket:
    return BuyerMarket(
        region_handle="region-1",
        country_code="gb",
        currency_code="gbp",
        sales_channel_handle="channel-1",
    )


@dataclass
class _ReadinessRuntime:
    initial_market: BuyerMarket
    store_error: SessionStoreError | None = None

    async def load_session(self):
        if self.store_error is not None:
            raise self.store_error
        return object()


@dataclass
class _RegionsClient:
    result: RegionsResult
    calls: int = 0

    async def list_regions(self) -> RegionsResult:
        self.calls += 1
        return self.result
