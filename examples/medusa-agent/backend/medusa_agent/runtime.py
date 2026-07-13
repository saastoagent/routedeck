from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from pathlib import Path

from routedeck_fastapi import InProcessEventNotifier, RouteDeckDependencies
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_sqlalchemy import (
    FernetSensitiveCodec,
    RouteDeckInstanceLeaseLost,
    UtcClock,
)

from .agent import create_live_medusa_agent, create_live_medusa_entry_agent
from .runtime_factory import MedusaRuntime, open_persistent_medusa_runtime
from .config import Settings
from .medusa.client.http import HttpMedusaStoreClient
from .medusa.client.models import Region
from .medusa.client.protocol import MedusaStoreClient
from .session import (
    BuyerMarket,
    MedusaSessionProjector,
    create_medusa_session,
)


class LiveRuntimeConfigurationError(RuntimeError):
    """Raised when explicit runtime configuration and real Medusa disagree."""


@dataclass(frozen=True)
class LiveMedusaReadiness:
    runtime: MedusaRuntime
    client: MedusaStoreClient
    settings: Settings

    async def routedeck_store_ready(self) -> bool:
        try:
            await self.runtime.load_session()
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
        return market == self.runtime.initial_market


@dataclass(frozen=True)
class LiveMedusaApplication:
    runtime: MedusaRuntime
    routedeck: RouteDeckDependencies
    agent: object | None
    entry_agent: object | None
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
    clock = UtcClock()
    notifier = InProcessEventNotifier()
    encryption_key = configured.routedeck_state_encryption_key.get_secret_value()
    runtime = await open_persistent_medusa_runtime(
        database_url=configured.routedeck_database_url,
        encryption_key=encryption_key,
        instance_id="medusa-agent-local",
        client=client,
        configured_payment_provider_id=configured.medusa_payment_provider_id,
        handlers={},
        providers={},
        guards={},
        clock=clock,
        notifier=notifier,
        id_factory=_new_runtime_id,
        review_ttl=timedelta(minutes=15),
        default_session_id="medusa-agent-default",
        market=market,
        worker_count=1,
    )
    try:
        projector = MedusaSessionProjector(runtime.app.app, clock)
        codec = FernetSensitiveCodec(encryption_key)
        dependencies = RouteDeckDependencies(
            app=runtime.app.app,
            runner=runtime.runner,
            store=runtime.store,
            notifier=notifier,
            projector=projector,
            private_form_codec=codec,
            session_factory=lambda session_id: create_medusa_session(
                session_id=session_id,
                market=market,
            ),
            navigation=runtime.navigation,
            session_initializer=runtime.initialize_session,
        )
        agent = _create_configured_agent(configured, runtime)
        entry_agent = _create_configured_entry_agent(configured)
        return LiveMedusaApplication(
            runtime=runtime,
            routedeck=dependencies,
            agent=agent,
            entry_agent=entry_agent,
            readiness=LiveMedusaReadiness(
                runtime=runtime,
                client=client,
                settings=configured,
            ),
        )
    except BaseException:
        await runtime.close()
        raise


def _create_configured_agent(
    settings: Settings, runtime: MedusaRuntime
) -> object | None:
    """Select the explicit agent execution mode without a fallback path."""

    mode = os.environ.get("ROUTEDECK_MODEL_MODE", "live")
    if mode == "live":
        return (
            None
            if settings.openai_api_key is None
            else create_live_medusa_agent(settings=settings, runtime=runtime)
        )
    if mode == "scripted-test-only":
        if os.environ.get("ROUTEDECK_TEST_ONLY") != "1":
            raise LiveRuntimeConfigurationError(
                "scripted-test-only model mode requires ROUTEDECK_TEST_ONLY=1"
            )
        support = import_module("routedeck_release_scripted_agent")
        factory = getattr(support, "create_scripted_test_agent", None)
        if factory is None or not callable(factory):
            raise LiveRuntimeConfigurationError(
                "scripted-test-only model support is not installed"
            )
        return factory(runtime=runtime)
    raise LiveRuntimeConfigurationError(
        "ROUTEDECK_MODEL_MODE must be 'live' or 'scripted-test-only'"
    )


def _create_configured_entry_agent(settings: Settings) -> object | None:
    """Select the explicit entry-agent execution mode without a fallback path."""

    mode = os.environ.get("ROUTEDECK_MODEL_MODE", "live")
    if mode == "live":
        return (
            None
            if settings.openai_api_key is None
            else create_live_medusa_entry_agent(settings=settings)
        )
    if mode == "scripted-test-only":
        if os.environ.get("ROUTEDECK_TEST_ONLY") != "1":
            raise LiveRuntimeConfigurationError(
                "scripted-test-only model mode requires ROUTEDECK_TEST_ONLY=1"
            )
        support = import_module("routedeck_release_scripted_agent")
        factory = getattr(support, "create_scripted_test_entry_agent", None)
        if factory is None or not callable(factory):
            raise LiveRuntimeConfigurationError(
                "scripted-test-only entry-agent support is not installed"
            )
        return factory()
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


def _new_runtime_id(kind: str) -> str:
    if not kind:
        raise ValueError("RouteDeck runtime ID kind must be non-empty")
    return f"{kind}_{secrets.token_urlsafe(18)}"


__all__ = [
    "LiveMedusaApplication",
    "LiveMedusaReadiness",
    "LiveRuntimeConfigurationError",
    "open_live_medusa_application",
]
