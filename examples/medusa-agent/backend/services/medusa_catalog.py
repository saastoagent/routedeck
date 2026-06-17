from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from core.config import Settings


@dataclass(frozen=True)
class MedusaCatalogProduct:
    handle: str
    title: str
    price: str
    summary: str
    colors: tuple[str, ...]
    sizes: tuple[str, ...]
    image_url: str
    image_source: str


@dataclass(frozen=True)
class MedusaCatalogSnapshot:
    products: tuple[MedusaCatalogProduct, ...]
    status: dict[str, object]


def load_medusa_catalog(settings: Settings | None = None) -> MedusaCatalogSnapshot:
    settings = settings or Settings.from_env()
    backend_url = _clean_url(settings.medusa_backend_url)
    publishable_key = settings.medusa_publishable_api_key

    if not backend_url or not publishable_key:
        return MedusaCatalogSnapshot(
            products=(),
            status={
                "ok": False,
                "source": "medusa_store_api",
                "code": "medusa_config_missing",
                "message": "MEDUSA_BACKEND_URL and MEDUSA_PUBLISHABLE_API_KEY are required to project the Medusa catalog.",
            },
        )

    try:
        with httpx.Client(timeout=settings.medusa_store_timeout_seconds, follow_redirects=True) as client:
            region_id = _default_region_id(client, backend_url, publishable_key)
            response = client.get(
                f"{backend_url}/store/products",
                headers={"x-publishable-api-key": publishable_key},
                params=_product_params(region_id),
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return MedusaCatalogSnapshot(
            products=(),
            status={
                "ok": False,
                "source": "medusa_store_api",
                "code": "medusa_store_http_error",
                "status_code": exc.response.status_code,
                "message": "Medusa Store API did not return a readable product catalog.",
            },
        )
    except httpx.RequestError:
        return MedusaCatalogSnapshot(
            products=(),
            status={
                "ok": False,
                "source": "medusa_store_api",
                "code": "medusa_store_unreachable",
                "message": "Medusa Store API could not be reached for product catalog projection.",
            },
        )

    payload = response.json()
    products = _normalize_products(payload.get("products") if isinstance(payload, dict) else None)
    return MedusaCatalogSnapshot(
        products=tuple(products),
        status={
            "ok": True,
            "source": "medusa_store_api",
            "code": "medusa_catalog_loaded",
            "count": len(products),
            "priced": all(product.price != "Price unavailable" for product in products),
        },
    )


def _default_region_id(client: httpx.Client, backend_url: str, publishable_key: str) -> str:
    response = client.get(
        f"{backend_url}/store/regions",
        headers={"x-publishable-api-key": publishable_key},
        params={"limit": 1},
    )
    response.raise_for_status()
    payload = response.json()
    regions = payload.get("regions") if isinstance(payload, dict) else None
    if not isinstance(regions, list) or not regions:
        return ""
    first_region = regions[0]
    return _string(first_region.get("id")) if isinstance(first_region, dict) else ""


def _product_params(region_id: str) -> dict[str, object]:
    params: dict[str, object] = {"limit": 12}
    if region_id:
        params["region_id"] = region_id
    return params


def _normalize_products(value: Any) -> list[MedusaCatalogProduct]:
    if not isinstance(value, list):
        return []

    products: list[MedusaCatalogProduct] = []
    for raw_product in value:
        product = _normalize_product(raw_product)
        if product:
            products.append(product)
    return products


def _normalize_product(value: Any) -> MedusaCatalogProduct | None:
    if not isinstance(value, dict):
        return None

    handle = _string(value.get("handle"))
    title = _string(value.get("title"))
    if not handle or not title:
        return None

    return MedusaCatalogProduct(
        handle=handle,
        title=title,
        price=_public_price(value),
        summary=_summary(value),
        colors=tuple(_option_values(value, "color")),
        sizes=tuple(_option_values(value, "size")),
        image_url=_image_url(value),
        image_source="medusa_store_api",
    )


def _summary(product: dict[str, Any]) -> str:
    return (
        _string(product.get("subtitle"))
        or _string(product.get("description"))
        or "Medusa catalog product."
    )


def _public_price(product: dict[str, Any]) -> str:
    for key in ("price", "display_price", "calculated_price"):
        price = _string(product.get(key))
        if price:
            return price

    variant_prices = [
        price
        for variant in product.get("variants", [])
        if isinstance(variant, dict)
        for price in [_variant_price(variant)]
        if price
    ]
    if variant_prices:
        return variant_prices[0]

    return "Price unavailable"


def _variant_price(variant: dict[str, Any]) -> str:
    calculated = variant.get("calculated_price")
    if not isinstance(calculated, dict):
        return ""
    amount = calculated.get("calculated_amount")
    currency_code = _string(calculated.get("currency_code"))
    if not isinstance(amount, (int, float)) or not currency_code:
        return ""
    return _format_money(float(amount), currency_code)


def _format_money(amount: float, currency_code: str) -> str:
    return f"{currency_code.upper()} {amount:,.2f}"


def _image_url(product: dict[str, Any]) -> str:
    thumbnail = _string(product.get("thumbnail"))
    if thumbnail:
        return thumbnail

    images = product.get("images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict):
                url = _string(image.get("url"))
                if url:
                    return url

    return ""


def _option_values(product: dict[str, Any], option_name: str) -> list[str]:
    values: list[str] = []
    options = product.get("options")
    if not isinstance(options, list):
        return values

    for option in options:
        if not isinstance(option, dict):
            continue
        title = _string(option.get("title")).lower()
        if title != option_name:
            continue
        option_values = option.get("values")
        if not isinstance(option_values, list):
            continue
        for value in option_values:
            if isinstance(value, dict):
                option_value = _string(value.get("value"))
                if option_value and option_value not in values:
                    values.append(option_value)
    return values


def _clean_url(value: str | None) -> str:
    return value.strip().rstrip("/") if isinstance(value, str) else ""


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
