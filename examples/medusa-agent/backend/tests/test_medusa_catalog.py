from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_load_medusa_catalog_reads_store_api_media_and_calculated_prices(monkeypatch):
    from core.config import Settings
    from services import medusa_catalog
    from services.medusa_catalog import load_medusa_catalog

    calls: list[dict[str, Any]] = []

    class FakeResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.status_code = 200
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def get(self, url: str, *, headers: dict[str, str], params: dict[str, Any]) -> FakeResponse:
            calls.append({"url": url, "headers": headers, "params": params})
            if url.endswith("/store/regions"):
                return FakeResponse({"regions": [{"id": "reg_eu"}]})
            return FakeResponse(
                {
                    "products": [
                        {
                            "id": "prod_private",
                            "handle": "shirt",
                            "title": "Store Shirt",
                            "description": "A product from Medusa.",
                            "thumbnail": "https://cdn.medusa.example/shirt.png",
                            "options": [
                                {"title": "Size", "values": [{"value": "S"}, {"value": "M"}]},
                                {"title": "Color", "values": [{"value": "Black"}]},
                            ],
                            "variants": [
                                {
                                    "id": "variant_private",
                                    "calculated_price": {
                                        "calculated_amount": 10,
                                        "currency_code": "eur",
                                    },
                                }
                            ],
                        }
                    ]
                }
            )

    monkeypatch.setattr(medusa_catalog.httpx, "Client", FakeClient)

    snapshot = load_medusa_catalog(
        Settings(
            medusa_backend_url="https://medusa.example/",
            medusa_publishable_api_key="pk_test",
        )
    )

    assert calls[0]["url"] == "https://medusa.example/store/regions"
    assert calls[1]["url"] == "https://medusa.example/store/products"
    assert calls[1]["headers"] == {"x-publishable-api-key": "pk_test"}
    assert calls[1]["params"] == {"limit": 12, "region_id": "reg_eu"}
    assert snapshot.status == {
        "ok": True,
        "source": "medusa_store_api",
        "code": "medusa_catalog_loaded",
        "count": 1,
        "priced": True,
    }

    product = snapshot.products[0]
    assert product.handle == "shirt"
    assert product.title == "Store Shirt"
    assert product.price == "EUR 10.00"
    assert product.summary == "A product from Medusa."
    assert product.colors == ("Black",)
    assert product.sizes == ("S", "M")
    assert product.image_url == "https://cdn.medusa.example/shirt.png"
    assert product.image_source == "medusa_store_api"
    assert "prod_private" not in str(product)
    assert "variant_private" not in str(product)


def test_load_medusa_catalog_requires_store_api_configuration():
    from core.config import Settings
    from services.medusa_catalog import load_medusa_catalog

    snapshot = load_medusa_catalog(Settings())

    assert snapshot.products == ()
    assert snapshot.status["ok"] is False
    assert snapshot.status["source"] == "medusa_store_api"
    assert snapshot.status["code"] == "medusa_config_missing"
