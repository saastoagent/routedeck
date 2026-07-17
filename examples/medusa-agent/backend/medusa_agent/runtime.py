from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from pathlib import Path

from routedeck_core import (
    RouteDeckRuntime,
    RouteDeckRuntimeServices,
)
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_langgraph import (
    RouteDeckLangGraphDriverFactory,
    RouteDeckLangGraphGraphs,
)
from routedeck_sqlalchemy import (
    RouteDeckInstanceLeaseLost,
    SqlAlchemyRuntimeResources,
    open_sqlalchemy_routedeck_runtime,
)

from .agent import create_live_medusa_agent, create_live_medusa_entry_agent
from .bindings import bind_medusa_app
from .composition import compile_medusa_app
from .config import Settings
from .features.catalog.providers import CatalogRouteKeyValidator
from .features.checkout.providers import EncryptedCheckoutPrivateFormReader
from .medusa.client.http import HttpMedusaStoreClient
from .medusa.client.models import Region
from .medusa.client.protocol import MedusaStoreClient
from .session import (
    BuyerMarket,
    create_medusa_session,
    initialize_medusa_session,
)
_READINESS_SESSION_ID = "routedeck-readiness-probe"


class LiveRuntimeConfigurationError(RuntimeError):
    """Raised when explicit runtime configuration and real Medusa disagree."""


@dataclass(frozen=True)
class LiveMedusaReadiness:
    runtime: RouteDeckRuntime
    client: MedusaStoreClient
    settings: Settings
    initial_market: BuyerMarket

    async def routedeck_store_ready(self) -> bool:
        try:
            await self.runtime.services.store.load(_READINESS_SESSION_ID)
        except SessionStoreError as error:
            return error.code in {
                SessionStoreErrorCode.SESSION_NOT_FOUND,
                SessionStoreErrorCode.SESSION_EXPIRED,
            }
        except RouteDeckInstanceLeaseLost:
            return False
        return True

    async def medusa_ready(self) -> bool:
        try:
            market = await _resolve_buyer_market(self.client, self.settings)
        except LiveRuntimeConfigurationError:
            return False
        return market == self.initial_market


@dataclass(frozen=True)
class LiveMedusaApplication:
    runtime: RouteDeckRuntime
    readiness: LiveMedusaReadiness

    async def close(self) -> None:
        await self.runtime.close()


async def open_live_medusa_application(
    settings: Settings | None = None,
) -> LiveMedusaApplication:
    configured = settings or Settings.from_env()
    release_bundle = os.environ.get("ROUTEDECK_RELEASE_BUNDLE")
    client: MedusaStoreClient
    if release_bundle:
        from .release_evidence import ReleaseMedusaEvidenceRecorder

        evidence_sink = ReleaseMedusaEvidenceRecorder(
            bundle_root=Path(release_bundle),
            configured_provider_id=configured.medusa_payment_provider_id,
        )
        client = HttpMedusaStoreClient(configured, evidence_sink=evidence_sink)
    else:
        client = HttpMedusaStoreClient(configured)
    market = await _resolve_buyer_market(client, configured)
    compiled = compile_medusa_app()

    def application_factory(
        resources: SqlAlchemyRuntimeResources,
    ):
        return bind_medusa_app(
            app=compiled,
            client=client,
            private_forms=EncryptedCheckoutPrivateFormReader(
                resources.store,
                resources.codec,
            ),
            configured_payment_provider_id=configured.medusa_payment_provider_id,
            buyer_country_code=market.country_code,
            handlers={},
            providers={},
            guards={},
        )

    runtime = await open_sqlalchemy_routedeck_runtime(
        compiled_app=compiled,
        application_factory=application_factory,
        session_factory=lambda app, session_id: create_medusa_session(
            app=app,
            session_id=session_id,
            market=market,
        ),
        session_initializer=initialize_medusa_session,
        public_key_validator_factory=CatalogRouteKeyValidator.from_session,
        agent_driver_factory=RouteDeckLangGraphDriverFactory(
            graph_factory=lambda services: _create_configured_graphs(
                configured,
                services,
            )
        ),
        database_url=configured.routedeck_database_url,
        encryption_key=configured.routedeck_state_encryption_key.get_secret_value(),
        instance_id="medusa-agent-local",
        review_ttl=timedelta(minutes=15),
        resume_capability_ttl=timedelta(hours=24),
        default_session_id="medusa-agent-default",
        worker_count=1,
    )
    return LiveMedusaApplication(
        runtime=runtime,
        readiness=LiveMedusaReadiness(
            runtime=runtime,
            client=client,
            settings=configured,
            initial_market=market,
        ),
    )


def _create_configured_graphs(
    settings: Settings,
    services: RouteDeckRuntimeServices,
) -> RouteDeckLangGraphGraphs | None:
    """Select one explicit product graph set without a fallback path."""

    mode = os.environ.get("ROUTEDECK_MODEL_MODE", "live")
    if mode == "live":
        if settings.openai_api_key is None:
            return None
        return RouteDeckLangGraphGraphs(
            user_message=create_live_medusa_agent(
                settings=settings,
                runtime=services,
            ),
            assistant_initiated=create_live_medusa_entry_agent(settings=settings),
            ignored_event_tags=frozenset(),
        )
    if mode == "scripted-test-only":
        if os.environ.get("ROUTEDECK_TEST_ONLY") != "1":
            raise LiveRuntimeConfigurationError(
                "scripted-test-only model mode requires ROUTEDECK_TEST_ONLY=1"
            )
        support = import_module("routedeck_release_scripted_agent")
        factory = getattr(support, "create_scripted_test_graphs", None)
        if factory is None or not callable(factory):
            raise LiveRuntimeConfigurationError(
                "scripted-test-only graph support is not installed"
            )
        graphs = factory(runtime=services)
        if not isinstance(graphs, RouteDeckLangGraphGraphs):
            raise LiveRuntimeConfigurationError(
                "scripted-test-only graph support returned an invalid graph set"
            )
        return graphs
    raise LiveRuntimeConfigurationError(
        "ROUTEDECK_MODEL_MODE must be 'live' or 'scripted-test-only'"
    )


async def _resolve_buyer_market(
    client: MedusaStoreClient,
    settings: Settings,
) -> BuyerMarket:
    result = await client.list_regions()
    if result.failure is not None:
        raise LiveRuntimeConfigurationError(
            f"Medusa region discovery failed with {result.failure.code}."
        )
    if result.value is None:
        raise LiveRuntimeConfigurationError(
            "Medusa region discovery returned no typed value."
        )
    matches = tuple(
        region
        for region in result.value
        if region.id.get_secret_value() == settings.medusa_region_id
    )
    if len(matches) != 1:
        raise LiveRuntimeConfigurationError(
            "MEDUSA_REGION_ID must identify exactly one Store region."
        )
    region = matches[0]
    _require_country(region, settings.medusa_country_code)
    return BuyerMarket(
        region_handle=settings.medusa_region_id,
        country_code=settings.medusa_country_code.lower(),
        currency_code=region.currency_code.lower(),
        sales_channel_handle=settings.medusa_sales_channel_id,
    )


def _require_country(region: Region, configured_country: str) -> None:
    country = configured_country.lower()
    if sum(item.iso_2.lower() == country for item in region.countries) != 1:
        raise LiveRuntimeConfigurationError(
            "MEDUSA_COUNTRY_CODE must identify one country in MEDUSA_REGION_ID."
        )


__all__ = [
    "LiveMedusaApplication",
    "LiveMedusaReadiness",
    "LiveRuntimeConfigurationError",
    "open_live_medusa_application",
]
