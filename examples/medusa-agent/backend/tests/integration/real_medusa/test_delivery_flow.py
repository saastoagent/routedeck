from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from medusa_agent.composition import compile_medusa_app
from medusa_agent.config import Settings
from medusa_agent.medusa.client import HttpMedusaStoreClient
from medusa_agent.session import BuyerMarket
from routedeck_core.app import ContextProviderHandler, GuardHandler, OperationHandler
from routedeck_core.contracts.events import RouteDeckEvent
from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationStatus,
)
from routedeck_core.contracts.operations import (
    DeliveryPhase,
    GuardRef,
    OperationDisposition,
    OperationOutcome,
    OperationRef,
    OperationRequest,
    OperationSource,
    ProviderRef,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.session import PrivateDraft
from routedeck_core.navigation.routes import RouteSessionContext
from routedeck_core.projection import ProjectionProjector
from routedeck_core.state import (
    RouteDeckSessionAggregate,
    TurnClaim,
    TurnOwnerKind,
)
from routedeck_core.supervision.guards import (
    GuardDecision,
    GuardInvocationContext,
    ProviderInvocationContext,
    ProviderResult,
)
from routedeck_langgraph import build_model_context
from routedeck_sqlalchemy import FernetSensitiveCodec
from support.runtime import open_test_runtime
from medusa_agent.medusa.client.models import (
    MedusaClientFailure,
    MedusaClientFailureKind,
    OrderPlaced,
    OrderResult,
)


_OWNED_OPERATION_IDS = {
    "cart.create",
    "cart.add_item",
    "cart.open",
    "cart.update_item",
    "cart.remove_item",
    "catalog.list",
    "catalog.search",
    "catalog.open_product",
    "catalog.open_product_by_route",
    "catalog.select_variant",
    "catalog.continue_shopping",
    "checkout.start",
    "checkout.save_contact",
    "checkout.select_shipping",
    "checkout.select_payment",
    "checkout.place_order",
    "orders.reconcile",
}
_OWNED_PROVIDER_IDS = {
    "cart.buyer_market",
    "cart.current",
    "cart.binding",
    "cart.items",
    "catalog.products",
    "catalog.product",
    "catalog.variants",
    "checkout.facts",
    "checkout.shipping_options",
    "checkout.payment_providers",
    "orders.confirmed_order",
}
_OWNED_GUARD_IDS = {
    "cart.absent",
    "cart.exists",
    "catalog.public_product",
    "catalog.variant_allowed",
    "checkout.cart_ready",
    "checkout.contact_valid",
    "checkout.shipping_valid",
    "checkout.payment_valid",
    "checkout.review_current",
}


@dataclass
class _CountingClient:
    delegate: HttpMedusaStoreClient
    calls: list[str] = field(default_factory=list)
    fail_next_order_read: bool = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    async def set_checkout_contact(self, cart_id: str, contact: Any) -> Any:
        self.calls.append("set_checkout_contact")
        return await self.delegate.set_checkout_contact(cart_id, contact)

    async def list_shipping_options(self, cart_id: str) -> Any:
        self.calls.append("list_shipping_options")
        return await self.delegate.list_shipping_options(cart_id)

    async def set_shipping_option(self, cart_id: str, option_id: str) -> Any:
        self.calls.append("set_shipping_option")
        return await self.delegate.set_shipping_option(cart_id, option_id)

    async def list_payment_providers(self, region_id: str) -> Any:
        self.calls.append("list_payment_providers")
        return await self.delegate.list_payment_providers(region_id)

    async def initialize_payment(self, cart: Any, provider_id: str) -> Any:
        self.calls.append("initialize_payment")
        return await self.delegate.initialize_payment(cart, provider_id)

    async def complete_cart(self, cart_id: str) -> Any:
        self.calls.append("complete_cart")
        result = await self.delegate.complete_cart(cart_id)
        if isinstance(result, OrderPlaced):
            self.fail_next_order_read = True
        return result

    async def get_order(self, order_id: str) -> Any:
        self.calls.append("get_order")
        if self.fail_next_order_read:
            self.fail_next_order_read = False
            return OrderResult.failed(
                delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
                failure=MedusaClientFailure(
                    kind=MedusaClientFailureKind.TRANSPORT,
                    code="injected_order_read_failure",
                    public_message="The order could not be read.",
                ),
            )
        return await self.delegate.get_order(order_id)


class _UnexpectedHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: Any,
    ) -> OperationOutcome:
        del arguments, context
        raise AssertionError("an unrelated operation executed in the delivery flow")


class _UnexpectedProvider:
    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        del context
        raise AssertionError("an unrelated provider executed in the delivery flow")


class _UnexpectedGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        del context
        raise AssertionError("an unrelated guard executed in the delivery flow")


@dataclass(frozen=True)
class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class _RecordingNotifier:
    events: list[RouteDeckEvent] = field(default_factory=list)

    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        del session_id
        self.events.extend(events)


@pytest.mark.asyncio
async def test_real_buyer_checkout_recovery_and_confirmation_flow(
    tmp_path: Path,
) -> None:
    settings = Settings.from_env()
    expected_base_url = os.environ.get(
        "ROUTEDECK_EXPECTED_MEDUSA_BASE_URL",
        "http://127.0.0.1:9100",
    ).rstrip("/")
    assert str(settings.medusa_base_url).rstrip("/") == expected_base_url
    client = _CountingClient(HttpMedusaStoreClient(settings))
    regions = await client.list_regions()
    assert regions.failure is None and regions.value is not None
    region = next(
        candidate
        for candidate in regions.value
        if candidate.id.get_secret_value() == settings.medusa_region_id
    )
    country_code = settings.medusa_country_code
    assert country_code in {country.iso_2.lower() for country in region.countries}
    market = BuyerMarket(
        region_handle=settings.medusa_region_id,
        country_code=country_code,
        currency_code=region.currency_code,
        sales_channel_handle=settings.medusa_sales_channel_id,
    )

    compiled = compile_medusa_app()
    handlers: dict[OperationRef, OperationHandler] = {
        operation.ref: _UnexpectedHandler()
        for operation in compiled.operations.values()
        if operation.id not in _OWNED_OPERATION_IDS
    }
    providers: dict[ProviderRef, ContextProviderHandler] = {
        provider.ref: _UnexpectedProvider()
        for provider in compiled.providers.values()
        if provider.id not in _OWNED_PROVIDER_IDS
    }
    guards: dict[GuardRef, GuardHandler] = {
        guard.ref: _UnexpectedGuard()
        for guard in compiled.guards.values()
        if guard.id not in _OWNED_GUARD_IDS
    }
    notifier = _RecordingNotifier()
    clock = _SystemClock()
    session_id = f"delivery-flow-{uuid4().hex}"
    database_path = tmp_path / "delivery-flow.sqlite"
    runtime = await open_test_runtime(
        database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
        encryption_key=settings.routedeck_state_encryption_key.get_secret_value(),
        instance_id=f"delivery-flow-instance-{uuid4().hex}",
        client=client,  # type: ignore[arg-type]
        configured_payment_provider_id=settings.medusa_payment_provider_id,
        handlers=handlers,
        providers=providers,
        guards=guards,
        clock=clock,
        notifier=notifier,
        id_factory=lambda kind: f"{kind}-{uuid4().hex}",
        review_ttl=timedelta(minutes=10),
        default_session_id=session_id,
        market=market,
    )

    private_email = "checkout-private@example.com"
    private_address = "47 Encrypted Avenue"
    private_phone = "+45 1234 5678"
    try:
        initial = runtime.session_factory(runtime.services.app.app, session_id)
        created = await runtime.services.store.create(initial)
        created = await runtime.session_initializer(runtime.services, created)
        private_cart_id = next(
            binding.private_id
            for binding in created.state.private_state.entity_bindings
            if binding.entity_kind == "cart"
        )

        await _run(runtime, "catalog.list", "delivery-catalog-list")
        snapshot = await runtime.services.store.load(session_id)
        product_ref = next(
            entity.handle
            for entity in snapshot.state.public_state.entity_handles
            if entity.entity_kind == "product"
        )
        await _run(
            runtime,
            "catalog.open_product",
            "delivery-product-open",
            {"product_ref": product_ref},
        )
        snapshot = await runtime.services.store.load(session_id)
        variant_ref = next(
            entity.handle
            for entity in snapshot.state.public_state.entity_handles
            if entity.entity_kind == "variant"
        )
        await _run(
            runtime,
            "cart.add_item",
            "delivery-cart-add",
            {"variant_ref": variant_ref, "quantity": 1},
        )
        await _run(runtime, "cart.open", "delivery-cart-open")
        await _run(runtime, "checkout.start", "delivery-checkout-start")

        contact_snapshot = await runtime.services.store.load(session_id)
        contact_projection = ProjectionProjector(
            runtime.services.app.app,
            now=clock.now(),
        ).project(contact_snapshot.state)
        contact_props = _public_values(contact_projection.surfaces.active.props)
        assert set(contact_props) == {
            "form_handle",
            "revision",
            "complete",
            "fields",
            "billing_choices",
            "default_billing_choice",
            "country_choices",
            "default_country_code",
        }
        assert contact_props["default_billing_choice"] == "same_as_shipping"
        assert contact_props["country_choices"] == [country_code]
        assert contact_props["default_country_code"] == country_code
        form_handle = contact_props["form_handle"]
        assert isinstance(form_handle, str) and form_handle.startswith("rdh_")

        contact_value = {
            "email": private_email,
            "shipping_address": {
                "first_name": "RouteDeck",
                "last_name": "Buyer",
                "address_1": private_address,
                "postal_code": "1000",
                "city": "Copenhagen",
                "country_code": country_code,
                "phone": private_phone,
            },
            "billing_choice": "same_as_shipping",
        }
        await _save_private_form(
            runtime,
            settings,
            form_handle,
            contact_value,
        )
        save_request = await _request(
            runtime,
            "checkout.save_contact",
            "delivery-contact-save",
            {"form_handle": form_handle},
        )
        assert private_email not in save_request.model_dump_json()
        assert private_address not in save_request.model_dump_json()
        saved = await runtime.services.runner.run(save_request)
        assert saved.disposition is OperationDisposition.COMPLETED, saved
        assert client.calls.count("set_checkout_contact") == 1
        assert client.calls.count("list_shipping_options") == 1

        delivery_snapshot = await runtime.services.store.load(session_id)
        delivery_projection = ProjectionProjector(
            runtime.services.app.app,
            now=clock.now(),
        ).project(delivery_snapshot.state)
        delivery_props = _public_values(delivery_projection.surfaces.active.props)
        assert delivery_props["state"] == "ready"
        assert len(delivery_props["options"]) == 2
        selected_ref = delivery_props["options"][0]["shipping_option_ref"]
        assert selected_ref.startswith("rdh_")

        selected = await _run(
            runtime,
            "checkout.select_shipping",
            "delivery-shipping-select",
            {"shipping_option_ref": selected_ref},
        )
        assert selected.disposition is OperationDisposition.COMPLETED
        assert client.calls.count("list_shipping_options") == 2
        assert client.calls.count("set_shipping_option") == 1

        final_snapshot = await runtime.services.store.load(session_id)
        final_projection = ProjectionProjector(
            runtime.services.app.app,
            now=clock.now(),
        ).project(final_snapshot.state)
        assert final_projection.current.node_id == "checkout.payment"
        current_resume = next(
            capability
            for capability in final_snapshot.state.private_state.resume_capabilities
            if capability.node_id == "checkout.payment"
        )
        reopen_url = runtime.services.app.app.routes.encode(
            "checkout.payment",
            {"resume_handle": current_resume.handle},
        )
        reopened = runtime.services.app.app.routes.decode(
            reopen_url,
            RouteSessionContext(
                guest_session_id=session_id,
                resume_capabilities=final_snapshot.state.private_state.resume_capabilities,
                now=clock.now(),
            ),
        )
        assert reopened.node_id == "checkout.payment"
        assert reopen_url.startswith("/checkout/payment?resume_handle=")

        real_cart = await client.get_cart(private_cart_id)
        assert real_cart.failure is None and real_cart.value is not None
        assert real_cart.value.email == private_email
        assert real_cart.value.shipping_address is not None
        assert real_cart.value.shipping_address.address_1 == private_address
        assert real_cart.value.shipping_methods

        payment_props = _public_values(final_projection.surfaces.active.props)
        assert payment_props["state"] == "ready"
        assert payment_props["providers"] == [
            {
                "payment_provider_ref": payment_props["providers"][0][
                    "payment_provider_ref"
                ],
                "label": "System / manual demo payment",
            }
        ]
        payment_ref = payment_props["providers"][0]["payment_provider_ref"]
        assert payment_ref.startswith("rdh_")
        payment_selected = await _run(
            runtime,
            "checkout.select_payment",
            "delivery-payment-select",
            {"payment_provider_ref": payment_ref},
        )
        assert payment_selected.disposition is OperationDisposition.COMPLETED
        assert client.calls.count("initialize_payment") == 1

        review_snapshot = await runtime.services.store.load(session_id)
        review_projection = ProjectionProjector(
            runtime.services.app.app,
            now=clock.now(),
        ).project(review_snapshot.state)
        assert review_projection.current.node_id == "checkout.review"
        order_review_props = _public_values(review_projection.surfaces.active.props)
        assert order_review_props["form_handle"] == form_handle
        assert order_review_props["items"]
        assert order_review_props["contact_complete"] is True
        assert order_review_props["billing_complete"] is True
        assert order_review_props["payment_label"] == ("System / manual demo payment")

        proposed = await runtime.services.runner.run(
            await _request(
                runtime,
                "checkout.place_order",
                "delivery-place-proposal",
            )
        )
        assert proposed.disposition is OperationDisposition.REQUIRES_REVIEW
        assert proposed.review is not None
        assert client.calls.count("complete_cart") == 0
        pending_snapshot = await runtime.services.store.load(session_id)
        pending_projection = ProjectionProjector(
            runtime.services.app.app,
            now=clock.now(),
        ).project(pending_snapshot.state)
        pending_props = _public_values(pending_projection.surfaces.review[0].props)
        assert pending_props["state"] == "pending"
        assert pending_props["review_id"] == proposed.review.id

        placed = await runtime.services.runner.accept_review(
            proposed.review.id,
            "delivery-place-accept",
            pending_snapshot.session_version,
            session_id=session_id,
        )
        assert placed.disposition is OperationDisposition.EXTERNAL_OUTCOME_UNKNOWN
        assert client.calls.count("complete_cart") == 1
        assert client.calls.count("get_order") == 1

        recovery_snapshot = await runtime.services.store.load(session_id)
        recovery_projection = ProjectionProjector(
            runtime.services.app.app,
            now=clock.now(),
        ).project(recovery_snapshot.state)
        recovery_surface = next(
            surface
            for surface in recovery_projection.surfaces.diagnostic
            if surface.surface_id == "checkout.recovery"
        )
        recovery_props = _public_values(recovery_surface.props)
        assert recovery_props["state"] == "external_outcome_unknown"
        order_ref = recovery_props["order_ref"]
        assert order_ref.startswith("rdh_")
        assert "checkout.place_order" in (
            recovery_snapshot.state.public_state.disabled_operation_ids
        )

        reconciled = await _run(
            runtime,
            "orders.reconcile",
            "delivery-order-reconcile",
            {"order_ref": order_ref},
        )
        assert reconciled.disposition is OperationDisposition.COMPLETED
        assert client.calls.count("complete_cart") == 1
        assert client.calls.count("get_order") == 2

        confirmation_snapshot = await runtime.services.store.load(session_id)
        confirmation_projection = ProjectionProjector(
            runtime.services.app.app,
            now=clock.now(),
        ).project(confirmation_snapshot.state)
        assert confirmation_projection.current.node_id == "orders.confirmation"
        confirmation_props = _public_values(
            confirmation_projection.surfaces.active.props
        )
        assert confirmation_props["confirmation_handle"] == order_ref
        assert confirmation_props["items"]
        assert confirmation_props["total"] == order_review_props["total"]
        assert confirmation_props["payment_label"] == ("System / manual demo payment")
        assert "checkout.place_order" not in (
            confirmation_snapshot.state.public_state.disabled_operation_ids
        )
        assert not any(
            binding.entity_kind
            in {
                "cart",
                "line_item",
                "shipping_option",
                "payment_provider",
            }
            for binding in confirmation_snapshot.state.private_state.entity_bindings
        )
        assert confirmation_snapshot.state.private_state.drafts == ()
        assert (
            await runtime.services.store.load_private_blob(session_id, form_handle)
            is None
        )

        continued = await _run(
            runtime,
            "catalog.continue_shopping",
            "delivery-continue-shopping",
        )
        assert continued.disposition is OperationDisposition.COMPLETED
        continued_snapshot = await runtime.services.store.load(session_id)
        continued_projection = ProjectionProjector(
            runtime.services.app.app,
            now=clock.now(),
        ).project(continued_snapshot.state)
        assert continued_projection.current.node_id == "catalog.browse"
        continued_props = _public_values(continued_projection.surfaces.active.props)
        assert continued_props["products"]
        assert not any(
            binding.entity_kind in {"order", "cart"}
            for binding in continued_snapshot.state.private_state.entity_bindings
        )

        model_context = build_model_context(
            continued_snapshot,
            runtime.services.app,
        )
        combined_public = "\n".join(
            (
                contact_projection.model_dump_json(),
                delivery_projection.model_dump_json(),
                final_projection.model_dump_json(),
                review_projection.model_dump_json(),
                pending_projection.model_dump_json(),
                recovery_projection.model_dump_json(),
                confirmation_projection.model_dump_json(),
                continued_projection.model_dump_json(),
                model_context.model_dump_json(),
                *(event.model_dump_json() for event in notifier.events),
                save_request.model_dump_json(),
                saved.model_dump_json(),
                selected.model_dump_json(),
                payment_selected.model_dump_json(),
                proposed.model_dump_json(),
                placed.model_dump_json(),
                reconciled.model_dump_json(),
                continued.model_dump_json(),
            )
        )
        for private_value in (private_email, private_address, private_phone):
            assert private_value not in combined_public
            assert private_value.encode("utf-8") not in database_path.read_bytes()

        stored = await runtime.services.store.find_attempt(
            session_id,
            "delivery-contact-save",
        )
        assert stored is not None
        assert private_email not in stored.model_dump_json()
        assert private_address not in stored.model_dump_json()
    finally:
        await runtime.close()


async def _save_private_form(
    runtime: Any,
    settings: Settings,
    form_handle: str,
    value: dict[str, Any],
) -> None:
    snapshot = await runtime.services.store.load(
        runtime.services.runner.default_session_id
    )
    draft = PrivateDraft(
        form_id=form_handle,
        field_names=tuple(sorted(value)),
        revision=1,
        complete=True,
    )
    next_state = (
        RouteDeckSessionAggregate(snapshot.state)
        .store_private_draft(draft)
        .commit()
    )
    serialized = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    codec = FernetSensitiveCodec(
        settings.routedeck_state_encryption_key.get_secret_value()
    )
    lease = await runtime.services.store.acquire_turn(
        TurnClaim(
            session_id=snapshot.session_id,
            expected_session_version=snapshot.session_version,
            request_id="delivery-private-form-save",
            request_fingerprint=hashlib.sha256(serialized).hexdigest(),
            owner_kind=TurnOwnerKind.SURFACE,
        )
    )
    try:
        await runtime.services.store.save_private_blob(
            lease,
            snapshot.session_version,
            form_handle,
            codec.encrypt(serialized),
            next_state,
            (),
            MutationCommit(
                kind=MutationKind.PRIVATE_FORM,
                status=MutationStatus.COMPLETED,
                result={
                    "complete": True,
                    "form_id": form_handle,
                    "revision": 1,
                },
            ),
        )
    finally:
        await runtime.services.store.release_turn(lease)


async def _request(
    runtime: Any,
    operation_id: str,
    request_id: str,
    arguments: Mapping[str, Any] | None = None,
) -> OperationRequest:
    snapshot = await runtime.services.store.load(
        runtime.services.runner.default_session_id
    )
    return OperationRequest(
        session_id=snapshot.session_id,
        request_id=request_id,
        expected_session_version=snapshot.session_version,
        operation_id=operation_id,
        source=OperationSource.SYSTEM,
        arguments=FrozenJsonObject(dict(arguments or {})),
    )


async def _run(
    runtime: Any,
    operation_id: str,
    request_id: str,
    arguments: Mapping[str, Any] | None = None,
) -> Any:
    result = await runtime.services.runner.run(
        await _request(runtime, operation_id, request_id, arguments)
    )
    assert result.disposition is OperationDisposition.COMPLETED, result
    return result


def _public_values(values: Any) -> dict[str, Any]:
    return {value.name: value.value.to_python() for value in values}
