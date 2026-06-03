from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from core.config import Settings


@dataclass(frozen=True)
class StoreVariant:
    id: str
    title: str
    options: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StoreProduct:
    id: str
    title: str
    description: str | None = None
    thumbnail: str | None = None
    variants: list[StoreVariant] = field(default_factory=list)


@dataclass(frozen=True)
class StoreRegion:
    id: str
    currency_code: str | None = None


@dataclass(frozen=True)
class StoreCartItem:
    id: str
    title: str | None = None
    quantity: int = 0
    variant_id: str | None = None


@dataclass(frozen=True)
class StoreCart:
    id: str
    items: list[StoreCartItem] = field(default_factory=list)


class MedusaStoreConfigurationError(RuntimeError):
    pass


class MedusaStoreClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if not self.settings.medusa_publishable_api_key:
            raise MedusaStoreConfigurationError("MEDUSA_PUBLISHABLE_API_KEY is required for Store API calls.")
        return {
            "Accept": "application/json",
            "x-publishable-api-key": self.settings.medusa_publishable_api_key,
        }

    def _base_url(self) -> str:
        return self.settings.medusa_backend_url.rstrip("/")

    async def list_products(self, limit: int = 12) -> list[StoreProduct]:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.get(f"{self._base_url()}/store/products", params={"limit": limit})
            response.raise_for_status()
        return [_parse_product(product) for product in response.json().get("products", [])]

    async def get_product(self, product_id: str) -> StoreProduct:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.get(f"{self._base_url()}/store/products/{product_id}")
            response.raise_for_status()
        return _parse_product(response.json()["product"])

    async def first_region(self) -> StoreRegion:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.get(f"{self._base_url()}/store/regions")
            response.raise_for_status()
        regions = response.json().get("regions", [])
        if not regions:
            raise ValueError("No Medusa Store API regions are available.")
        return StoreRegion(id=regions[0]["id"], currency_code=regions[0].get("currency_code"))

    async def create_cart(self, region_id: str) -> StoreCart:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.post(f"{self._base_url()}/store/carts", json={"region_id": region_id})
            response.raise_for_status()
        return _parse_cart(response.json()["cart"])

    async def add_line_item(self, cart_id: str, variant_id: str, quantity: int) -> StoreCart:
        async with httpx.AsyncClient(transport=self.transport, timeout=5.0, headers=self._headers()) as client:
            response = await client.post(
                f"{self._base_url()}/store/carts/{cart_id}/line-items",
                json={"variant_id": variant_id, "quantity": quantity},
            )
            response.raise_for_status()
        return _parse_cart(response.json()["cart"])


def _parse_product(raw: dict[str, Any]) -> StoreProduct:
    return StoreProduct(
        id=raw["id"],
        title=raw.get("title") or "Untitled product",
        description=raw.get("description"),
        thumbnail=raw.get("thumbnail"),
        variants=[
            StoreVariant(
                id=variant["id"],
                title=variant.get("title") or "Default",
                options=[str(option.get("value")) for option in variant.get("options", []) if option.get("value")],
            )
            for variant in raw.get("variants", [])
        ],
    )


def _parse_cart(raw: dict[str, Any]) -> StoreCart:
    return StoreCart(
        id=raw["id"],
        items=[
            StoreCartItem(
                id=item["id"],
                title=item.get("title"),
                quantity=int(item.get("quantity") or 0),
                variant_id=item.get("variant_id"),
            )
            for item in raw.get("items", [])
        ],
    )
