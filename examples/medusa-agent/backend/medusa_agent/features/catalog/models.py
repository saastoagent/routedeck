from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class _CatalogContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class InventoryStatus(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class CatalogPrice(_CatalogContract):
    amount: int = Field(ge=0)
    currency_code: str = Field(min_length=3, max_length=3)


class CatalogOption(_CatalogContract):
    title: str = Field(min_length=1)
    values: tuple[str, ...]


class CatalogProductCard(_CatalogContract):
    interaction_handle: str = Field(min_length=1)
    product_handle: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    thumbnail_url: str | None = Field(default=None, min_length=1)
    price: CatalogPrice
    variant_count: int = Field(ge=1)


class CatalogVariant(_CatalogContract):
    interaction_handle: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sku: str | None = Field(default=None, min_length=1)
    price: CatalogPrice
    inventory_status: InventoryStatus
    inventory_quantity: int | None = None
    option_values: tuple[str, ...] = ()


class CatalogProductDetail(_CatalogContract):
    interaction_handle: str = Field(min_length=1)
    product_handle: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    thumbnail_url: str | None = Field(default=None, min_length=1)
    image_urls: tuple[str, ...] = ()
    options: tuple[CatalogOption, ...] = ()
    variants: tuple[CatalogVariant, ...] = Field(min_length=1)
    selected_variant_handle: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _selected_variant_exists(self) -> CatalogProductDetail:
        handles = tuple(variant.interaction_handle for variant in self.variants)
        if len(handles) != len(set(handles)):
            raise ValueError("catalog variant interaction handles must be unique")
        if (
            self.selected_variant_handle is not None
            and self.selected_variant_handle not in handles
        ):
            raise ValueError("selected variant must belong to the product")
        return self


class CatalogCollectionObservation(_CatalogContract):
    products: tuple[CatalogProductCard, ...]
    count: int = Field(ge=0)
    query: str | None = Field(default=None, min_length=1)


class CatalogProductObservation(_CatalogContract):
    product: CatalogProductDetail


class CatalogSelectionObservation(_CatalogContract):
    product_handle: str = Field(min_length=1)
    variant_handle: str = Field(min_length=1)


class CatalogPrivateBinding(_CatalogContract):
    entity_kind: str = Field(min_length=1)
    interaction_handle: str = Field(min_length=1)
    private_id: SecretStr = Field(min_length=1)

    def provider_dict(self) -> dict[str, str]:
        return {
            "entity_kind": self.entity_kind,
            "interaction_handle": self.interaction_handle,
            "private_id": self.private_id.get_secret_value(),
        }


class CatalogCollectionProviderValue(_CatalogContract):
    observation: CatalogCollectionObservation
    bindings: tuple[CatalogPrivateBinding, ...]

    @model_validator(mode="after")
    def _one_binding_per_product(self) -> CatalogCollectionProviderValue:
        handles = {product.interaction_handle for product in self.observation.products}
        bound = {binding.interaction_handle for binding in self.bindings}
        if handles != bound or any(
            binding.entity_kind != "product" for binding in self.bindings
        ):
            raise ValueError("catalog collection bindings must match its products")
        return self

    def provider_dict(self) -> dict[str, object]:
        return {
            "observation": self.observation.model_dump(mode="json", exclude_none=True),
            "bindings": [binding.provider_dict() for binding in self.bindings],
        }


class CatalogProductProviderValue(_CatalogContract):
    observation: CatalogProductObservation
    product_binding: CatalogPrivateBinding
    variant_bindings: tuple[CatalogPrivateBinding, ...]

    @model_validator(mode="after")
    def _bindings_match_detail(self) -> CatalogProductProviderValue:
        product = self.observation.product
        if (
            self.product_binding.entity_kind != "product"
            or self.product_binding.interaction_handle != product.interaction_handle
        ):
            raise ValueError("catalog product binding must match its detail")
        handles = {variant.interaction_handle for variant in product.variants}
        bound = {binding.interaction_handle for binding in self.variant_bindings}
        if handles != bound or any(
            binding.entity_kind != "variant" for binding in self.variant_bindings
        ):
            raise ValueError("catalog variant bindings must match product variants")
        return self

    def provider_dict(self) -> dict[str, object]:
        return {
            "observation": self.observation.model_dump(mode="json", exclude_none=True),
            "product_binding": self.product_binding.provider_dict(),
            "variant_bindings": [
                binding.provider_dict() for binding in self.variant_bindings
            ],
        }


PRICE_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "integer", "minimum": 0},
        "currency_code": {"type": "string", "minLength": 3, "maxLength": 3},
    },
    "required": ["amount", "currency_code"],
    "additionalProperties": False,
}

PRODUCT_CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "interaction_handle": {"type": "string", "minLength": 1},
        "product_handle": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "thumbnail_url": {"type": "string", "minLength": 1},
        "price": PRICE_SCHEMA,
        "variant_count": {"type": "integer", "minimum": 1},
    },
    "required": [
        "interaction_handle",
        "product_handle",
        "title",
        "price",
        "variant_count",
    ],
    "additionalProperties": False,
}

CATALOG_COLLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "products": {"type": "array", "items": PRODUCT_CARD_SCHEMA},
        "count": {"type": "integer", "minimum": 0},
        "query": {"type": "string", "minLength": 1},
    },
    "required": ["products", "count"],
    "additionalProperties": False,
}

OPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "values": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
    "required": ["title", "values"],
    "additionalProperties": False,
}

VARIANT_SCHEMA = {
    "type": "object",
    "properties": {
        "interaction_handle": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "sku": {"type": "string", "minLength": 1},
        "price": PRICE_SCHEMA,
        "inventory_status": {
            "type": "string",
            "enum": [status.value for status in InventoryStatus],
        },
        "inventory_quantity": {"type": "integer"},
        "option_values": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
    "required": [
        "interaction_handle",
        "title",
        "price",
        "inventory_status",
        "option_values",
    ],
    "additionalProperties": False,
}

PRODUCT_DETAIL_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "interaction_handle": {"type": "string", "minLength": 1},
        "product_handle": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "thumbnail_url": {"type": "string", "minLength": 1},
        "image_urls": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "options": {"type": "array", "items": OPTION_SCHEMA},
        "variants": {
            "type": "array",
            "minItems": 1,
            "items": VARIANT_SCHEMA,
        },
        "selected_variant_handle": {"type": "string", "minLength": 1},
    },
    "required": [
        "interaction_handle",
        "product_handle",
        "title",
        "image_urls",
        "options",
        "variants",
    ],
    "additionalProperties": False,
}

CATALOG_PRODUCT_SCHEMA = {
    "type": "object",
    "properties": {"product": PRODUCT_DETAIL_VALUE_SCHEMA},
    "required": ["product"],
    "additionalProperties": False,
}

CATALOG_SELECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "product_handle": {"type": "string", "minLength": 1},
        "variant_handle": {"type": "string", "minLength": 1},
    },
    "required": ["product_handle", "variant_handle"],
    "additionalProperties": False,
}

PRIVATE_BINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "entity_kind": {"type": "string", "minLength": 1},
        "interaction_handle": {"type": "string", "minLength": 1},
        "private_id": {"type": "string", "minLength": 1},
    },
    "required": ["entity_kind", "interaction_handle", "private_id"],
    "additionalProperties": False,
}

CATALOG_COLLECTION_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "observation": CATALOG_COLLECTION_SCHEMA,
        "bindings": {"type": "array", "items": PRIVATE_BINDING_SCHEMA},
    },
    "required": ["observation", "bindings"],
    "additionalProperties": False,
}

CATALOG_PRODUCT_PROVIDER_SCHEMA = {
    "type": "object",
    "properties": {
        "observation": CATALOG_PRODUCT_SCHEMA,
        "product_binding": PRIVATE_BINDING_SCHEMA,
        "variant_bindings": {
            "type": "array",
            "minItems": 1,
            "items": PRIVATE_BINDING_SCHEMA,
        },
    },
    "required": ["observation", "product_binding", "variant_bindings"],
    "additionalProperties": False,
}


__all__ = [
    "CATALOG_COLLECTION_PROVIDER_SCHEMA",
    "CATALOG_COLLECTION_SCHEMA",
    "CATALOG_PRODUCT_PROVIDER_SCHEMA",
    "CATALOG_PRODUCT_SCHEMA",
    "CATALOG_SELECTION_SCHEMA",
    "CatalogCollectionObservation",
    "CatalogCollectionProviderValue",
    "CatalogOption",
    "CatalogPrice",
    "CatalogPrivateBinding",
    "CatalogProductCard",
    "CatalogProductDetail",
    "CatalogProductObservation",
    "CatalogProductProviderValue",
    "CatalogSelectionObservation",
    "CatalogVariant",
    "InventoryStatus",
]
