from __future__ import annotations

from dataclasses import dataclass, field, replace

import pytest
from pydantic import SecretStr, ValidationError

from medusa_agent.features.cart.operations import CreateCartHandler
from medusa_agent.medusa.client.models import (
    CreateCartRequest,
    CreateCartResult,
    MedusaCart,
    MedusaClientFailure,
    MedusaClientFailureKind,
)
from medusa_agent.medusa.client.protocol import MedusaStoreClient
from medusa_agent.session import create_medusa_session, initialize_medusa_session
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import DeliveryPhase
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationEvidence,
    OperationPhase,
    OperationRequest,
    OperationResult,
    OperationSource,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.ports.executor import ExecutionContext
from support.medusa import RecordingMedusaStoreClient, buyer_market, cart
from support.runtime import (
    RecordingNotifier,
    build_test_runtime,
    operation_request,
)


@dataclass
class _InitializationRunner:
    result: OperationResult
    requests: list[OperationRequest] = field(default_factory=list)

    async def run(self, request: OperationRequest) -> OperationResult:
        self.requests.append(request)
        return self.result


class _InitializationStore:
    async def load(self, session_id: str) -> SessionSnapshot:
        del session_id
        raise AssertionError("failed cart initialization must not return a snapshot")


def test_recording_client_satisfies_the_typed_store_protocol() -> None:
    client = RecordingMedusaStoreClient(
        create_cart_result=CreateCartResult.succeeded(cart())
    )

    assert isinstance(client, MedusaStoreClient)


def test_medusa_cart_requires_a_nonempty_private_identity() -> None:
    with pytest.raises(ValidationError):
        MedusaCart(id=SecretStr(""), currency_code="qzx")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "delivery_phase",
    (DeliveryPhase.NOT_SENT, DeliveryPhase.POSSIBLY_SENT),
)
async def test_cart_handler_preserves_typed_delivery_failure(
    delivery_phase: DeliveryPhase,
) -> None:
    client = RecordingMedusaStoreClient(
        create_cart_result=CreateCartResult.failed(
            delivery_phase=delivery_phase,
            failure=MedusaClientFailure(
                kind=MedusaClientFailureKind.TRANSPORT,
                code="medusa_unavailable",
                public_message="The cart service is unavailable.",
            ),
        )
    )
    context = ExecutionContext(
        session_id="session-1",
        request_id="request-1",
        attempt_id="attempt-1",
        node_id="catalog.product",
        source=OperationSource.SYSTEM,
        context_fingerprint="context-1",
        provider_values=FrozenJsonObject(
            {
                "cart.buyer_market": {
                    "region_id": "private-region-sentinel",
                    "country_code": "zx",
                    "sales_channel_id": "private-channel-sentinel",
                }
            }
        ),
    )

    outcome = await CreateCartHandler(client)({}, context)

    assert outcome.delivery_phase is delivery_phase
    assert outcome.failure is not None
    assert outcome.failure.code == "medusa_unavailable"
    assert outcome.failure.safe_details.delivery_phase == delivery_phase.value
    assert client.calls == ["create_cart"]


@pytest.mark.asyncio
async def test_medusa_cart_create_binding_cannot_bypass_runner() -> None:
    market = buyer_market()
    client = RecordingMedusaStoreClient(
        create_cart_result=CreateCartResult.succeeded(cart())
    )
    runtime = build_test_runtime(client=client, market=market)

    result = await runtime.services.runner.run(
        operation_request(
            operation_id="cart.create",
            source=OperationSource.SYSTEM,
            request_id="cart-create-1",
        )
    )

    assert result.disposition is OperationDisposition.COMPLETED
    assert result.outcome == "created"
    assert client.calls == ["create_cart"]
    assert client.create_cart_requests == [
        CreateCartRequest(
            region_id=market.region_handle,
            country_code=market.country_code,
            sales_channel_id=market.sales_channel_handle,
        )
    ]
    assert result.evidence.source is OperationSource.SYSTEM
    stored = await runtime.services.store.find_attempt("session-1", "cart-create-1")
    assert stored is not None
    assert stored.journaled_result is not None
    assert stored.journaled_result.observation.to_dict() == {
        "cart_id": client.created_cart.id.get_secret_value(),
        "currency_code": client.created_cart.currency_code,
    }
    assert client.created_cart.id.get_secret_value() not in result.model_dump_json()
    notifier = runtime.services.notifier
    assert isinstance(notifier, RecordingNotifier)
    assert all(
        client.created_cart.id.get_secret_value() not in event.model_dump_json()
        for _, events in notifier.notifications
        for event in events
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("disposition", "kind"),
    (
        (OperationDisposition.FAILED, FailureKind.TRANSPORT),
        (
            OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN,
            FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
        ),
    ),
)
async def test_failed_or_unknown_initial_cart_never_returns_a_session(
    disposition: OperationDisposition,
    kind: FailureKind,
) -> None:
    market = buyer_market()
    runtime = build_test_runtime(
        client=RecordingMedusaStoreClient(
            create_cart_result=CreateCartResult.succeeded(cart())
        ),
        market=market,
    )
    session = create_medusa_session(
        app=runtime.services.app.app,
        session_id="session-bootstrap",
        market=market,
    )
    runner = _InitializationRunner(
        OperationResult(
            disposition=disposition,
            session_id=session.session_id,
            request_id="initial-cart-result",
            operation_id="cart.create",
            session_version=session.session_version,
            projection_version=session.projection_version,
            evidence=OperationEvidence(
                source=OperationSource.SYSTEM,
                phases=(OperationPhase.RECEIVED,),
                attempt_id="attempt-bootstrap",
                request_fingerprint="fingerprint-bootstrap",
            ),
            failure=RouteDeckFailure(
                kind=kind,
                code="initial_cart_unproved",
                phase="execute",
                correlation_id="correlation-bootstrap",
                operation_id="cart.create",
                request_id="initial-cart-result",
                public_message="The buyer cart could not be initialized.",
            ),
        )
    )
    services = replace(
        runtime.services,
        runner=runner,  # type: ignore[arg-type]
        store=_InitializationStore(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="did not prove cart creation"):
        await initialize_medusa_session(services, SessionSnapshot(state=session))

    assert len(runner.requests) == 1
    request = runner.requests[0]
    assert request.operation_id == "cart.create"
    assert request.source is OperationSource.SYSTEM
