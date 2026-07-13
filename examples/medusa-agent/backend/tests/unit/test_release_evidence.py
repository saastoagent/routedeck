from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from medusa_agent.config import Settings
from medusa_agent.medusa.client.http import HttpMedusaStoreClient
from medusa_agent.medusa.client.models import OrderPlaced
from medusa_agent.release_evidence import ReleaseMedusaEvidenceRecorder


@pytest.mark.asyncio
async def test_release_client_measures_completion_and_independent_reread(
    tmp_path: Path,
) -> None:
    order = _order_payload()
    calls: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(200, json={"type": "order", "order": order})
        return httpx.Response(200, json={"order": order})

    settings = _settings(tmp_path)
    recorder = ReleaseMedusaEvidenceRecorder(
        bundle_root=tmp_path / "release",
        configured_provider_id=settings.medusa_payment_provider_id,
    )
    client = HttpMedusaStoreClient(
        settings,
        transport=httpx.MockTransport(handler),
        evidence_sink=recorder,
    )

    completion = await client.complete_cart("cart_private_1234567890123456")
    assert isinstance(completion, OrderPlaced)
    result = await client.get_order("order_private_1234567890123456")
    assert result.failure is None
    assert calls == [
        ("POST", "/store/carts/cart_private_1234567890123456/complete"),
        ("GET", "/store/orders/order_private_1234567890123456"),
    ]

    proof_path = tmp_path / "release" / "medusa" / "order-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof == {
        "schema_version": 1,
        "status": "fail",
        "source": "measured_typed_medusa_store_calls",
        "transport_kind": "injected",
        "completion_type": "order",
        "complete_cart_call_count": 1,
        "get_order_call_count_after_completion": 1,
        "independent_order_reread": True,
        "order_identity_match": True,
        "items_match": True,
        "quantities_match": True,
        "totals_match": True,
        "email_match": True,
        "shipping_method_match": True,
        "payment_provider_match": True,
    }
    trace = (tmp_path / "release" / "medusa" / "store-api-trace.ndjson").read_text(
        encoding="utf-8"
    )
    assert "cart_private" not in trace
    assert "order_private" not in trace
    assert "buyer@example.test" not in trace
    assert '"transport_kind":"injected"' in trace


def _settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "medusa_base_url": "http://medusa.test",
            "medusa_publishable_key": "pk_test_private",
            "medusa_region_id": "reg_private_1234567890123456",
            "medusa_country_code": "us",
            "medusa_sales_channel_id": "sc_private_1234567890123456",
            "medusa_payment_provider_id": "pp_system_default",
            "routedeck_database_url": (
                "sqlite+pysqlite:///" + (tmp_path / "routedeck.sqlite").as_posix()
            ),
            "routedeck_state_encryption_key": "test-only-key",
            "openai_api_key": None,
            "openai_model": "test-only-model",
        }
    )


def _order_payload() -> dict[str, object]:
    return {
        "id": "order_private_1234567890123456",
        "status": "pending",
        "display_id": 42,
        "currency_code": "usd",
        "region_id": "reg_private_1234567890123456",
        "email": "buyer@example.test",
        "total": 5500,
        "subtotal": 5500,
        "item_subtotal": 5000,
        "tax_total": 0,
        "discount_total": 0,
        "shipping_total": 500,
        "items": [
            {
                "id": "item_private_1234567890123456",
                "variant_id": "variant_private_1234567890123456",
                "title": "Linen shirt",
                "quantity": 1,
                "unit_price": 5000,
                "total": 5000,
            }
        ],
        "shipping_methods": [
            {
                "shipping_option_id": "so_private_1234567890123456",
                "name": "Standard",
                "amount": 500,
            }
        ],
        "payment_collections": [
            {
                "id": "pay_private_1234567890123456",
                "currency_code": "usd",
                "amount": 5500,
                "payment_sessions": [
                    {
                        "id": "pay_session_private_1234567890123456",
                        "provider_id": "pp_system_default",
                        "status": "pending",
                    }
                ],
            }
        ],
    }
