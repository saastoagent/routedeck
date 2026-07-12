from __future__ import annotations

from dataclasses import dataclass

from pydantic import SecretStr

from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.session import RouteDeckSession
from routedeck_core.handles import new_opaque_handle
from routedeck_core.supervision.guards import (
    ProviderInvocationContext,
    ProviderResult,
)

from ...medusa.client.models import (
    Product,
    ProductPageResult,
    ProductQuery,
    ProductResult,
    ProductVariant,
)
from ...medusa.client.protocol import MedusaStoreClient
from .feature import (
    CATALOG_LIST,
    CATALOG_SEARCH,
    CONTINUE_SHOPPING,
    OPEN_PRODUCT,
    OPEN_PRODUCT_BY_ROUTE,
    PRODUCT_DETAIL,
)
from .models import (
    CatalogCollectionObservation,
    CatalogCollectionProviderValue,
    CatalogOption,
    CatalogPrice,
    CatalogPrivateBinding,
    CatalogProductCard,
    CatalogProductDetail,
    CatalogProductObservation,
    CatalogProductProviderValue,
    CatalogVariant,
    InventoryStatus,
)


class CatalogProviderError(RuntimeError):
    """Sanitized fail-loud catalog provider failure."""


@dataclass(frozen=True)
class CatalogRouteKeyValidator:
    """Validate shareable product keys against authoritative observed products."""

    product_handles: frozenset[str]

    def is_valid(self, key: str, value: str) -> bool:
        return key == "product_handle" and value in self.product_handles

    @classmethod
    def from_session(cls, session: RouteDeckSession) -> CatalogRouteKeyValidator:
        product_handles: set[str] = set()
        for entity in session.public_state.entity_handles:
            if entity.entity_kind != "product":
                continue
            values = {value.name: value.value.to_python() for value in entity.values}
            product_handle = values.get("product_handle")
            if isinstance(product_handle, str) and product_handle:
                product_handles.add(product_handle)
        for surface in session.public_state.surface_state:
            values = {value.name: value.value.to_python() for value in surface.values}
            if surface.surface_id == "catalog.product_grid":
                collection = CatalogCollectionObservation.model_validate(values)
                product_handles.update(
                    product.product_handle for product in collection.products
                )
            elif surface.surface_id == PRODUCT_DETAIL.id:
                detail = CatalogProductObservation.model_validate(values)
                product_handles.add(detail.product.product_handle)
        return cls(product_handles=frozenset(product_handles))


@dataclass(frozen=True)
class CatalogProvider:
    """Load one authoritative Medusa collection or product detail."""

    client: MedusaStoreClient

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        operation_id = context.request.operation_id
        if operation_id in {
            CATALOG_LIST.id,
            CATALOG_SEARCH.id,
            CONTINUE_SHOPPING.id,
        }:
            return await self._collection(context)
        if operation_id == OPEN_PRODUCT.id:
            return await self._product_from_interaction(context)
        if operation_id == OPEN_PRODUCT_BY_ROUTE.id:
            return await self._product_from_route(context)
        raise CatalogProviderError(
            f"catalog provider is not declared for {operation_id!r}"
        )

    async def _collection(
        self,
        context: ProviderInvocationContext,
    ) -> ProviderResult:
        query_value: str | None = None
        if context.request.operation_id == CATALOG_SEARCH.id:
            raw_query = context.request.arguments.to_dict().get("query")
            if not isinstance(raw_query, str) or not raw_query:
                raise CatalogProviderError("catalog search requires one exact query")
            query_value = raw_query
        region_id = _market_region_id(context.session)
        result = await self.client.list_products(
            ProductQuery(region_id=region_id, query=query_value)
        )
        if not isinstance(result, ProductPageResult):
            raise CatalogProviderError(
                "MedusaStoreClient.list_products returned an invalid result"
            )
        if result.failure is not None:
            raise CatalogProviderError(
                f"{result.failure.code}: {result.failure.public_message}"
            )
        page = result.value
        if page is None:
            raise CatalogProviderError("successful product collection is missing")

        cards: list[CatalogProductCard] = []
        bindings: list[CatalogPrivateBinding] = []
        for product in page.products:
            private_id = product.id.get_secret_value()
            interaction_handle = _existing_or_new_handle(
                context.session,
                entity_kind="product",
                private_id=private_id,
            )
            cards.append(_product_card(product, interaction_handle))
            bindings.append(
                CatalogPrivateBinding(
                    entity_kind="product",
                    interaction_handle=interaction_handle,
                    private_id=SecretStr(private_id),
                )
            )
        value = CatalogCollectionProviderValue(
            observation=CatalogCollectionObservation(
                products=tuple(cards),
                count=page.count,
                query=query_value,
            ),
            bindings=tuple(bindings),
        )
        return ProviderResult(values=FrozenJsonObject(value.provider_dict()))

    async def _product_from_interaction(
        self,
        context: ProviderInvocationContext,
    ) -> ProviderResult:
        requested_interaction_handle = context.request.arguments.to_dict().get(
            "product_ref"
        )
        if not isinstance(requested_interaction_handle, str):
            raise CatalogProviderError("catalog product interaction handle is missing")
        public_product_handle = _public_product_handle(
            context.session,
            requested_interaction_handle,
        )
        region_id = _market_region_id(context.session)
        product = await self._load_product(public_product_handle, region_id)
        value = _product_provider_value(context.session, product)
        if value.product_binding.interaction_handle != requested_interaction_handle:
            raise CatalogProviderError(
                "authoritative product binding changed during detail refresh"
            )
        return ProviderResult(values=FrozenJsonObject(value.provider_dict()))

    async def _product_from_route(
        self,
        context: ProviderInvocationContext,
    ) -> ProviderResult:
        public_product_handle = context.request.arguments.to_dict().get(
            "product_handle"
        )
        if not isinstance(public_product_handle, str) or not public_product_handle:
            raise CatalogProviderError("catalog product route handle is missing")
        region_id = _market_region_id(context.session)
        product = await self._load_product(public_product_handle, region_id)
        value = _product_provider_value(context.session, product)
        return ProviderResult(values=FrozenJsonObject(value.provider_dict()))

    async def _load_product(self, handle: str, region_id: str) -> Product:
        result = await self.client.get_product(handle, region_id)
        if not isinstance(result, ProductResult):
            raise CatalogProviderError(
                "MedusaStoreClient.get_product returned an invalid result"
            )
        if result.failure is not None:
            raise CatalogProviderError(
                f"{result.failure.code}: {result.failure.public_message}"
            )
        product = result.value
        if product is None:
            raise CatalogProviderError("successful product detail is missing")
        if product.handle != handle:
            raise CatalogProviderError(
                "Medusa product handle did not match the request"
            )
        return product


class CurrentCatalogProductProvider:
    """Read the current projected detail for a selection-only operation."""

    async def __call__(self, context: ProviderInvocationContext) -> ProviderResult:
        surface = next(
            (
                candidate
                for candidate in context.session.public_state.surface_state
                if candidate.surface_id == PRODUCT_DETAIL.id
            ),
            None,
        )
        if surface is None:
            raise CatalogProviderError("current catalog product detail is unavailable")
        values = {value.name: value.value.to_python() for value in surface.values}
        observation = CatalogProductObservation.model_validate(values)
        return ProviderResult(
            values=FrozenJsonObject(
                observation.model_dump(mode="json", exclude_none=True)
            )
        )


def _market_region_id(session: RouteDeckSession) -> str:
    configuration = next(
        (
            candidate
            for candidate in session.private_state.configurations
            if candidate.namespace == "medusa.buyer_market"
        ),
        None,
    )
    if configuration is None:
        raise CatalogProviderError("buyer market configuration is unavailable")
    field = next(
        (
            candidate
            for candidate in configuration.fields
            if candidate.name == "region_handle"
        ),
        None,
    )
    value = field.value.to_python() if field is not None else None
    if not isinstance(value, str) or not value:
        raise CatalogProviderError("buyer market region is unavailable")
    return value


def _public_product_handle(
    session: RouteDeckSession,
    interaction_handle: str,
) -> str:
    matches = tuple(
        entity
        for entity in session.public_state.entity_handles
        if entity.entity_kind == "product" and entity.handle == interaction_handle
    )
    if len(matches) != 1:
        raise CatalogProviderError("catalog product interaction handle is unavailable")
    values = {value.name: value.value.to_python() for value in matches[0].values}
    product_handle = values.get("product_handle")
    if not isinstance(product_handle, str) or not product_handle:
        raise CatalogProviderError("catalog product has no public route handle")
    return product_handle


def _existing_or_new_handle(
    session: RouteDeckSession,
    *,
    entity_kind: str,
    private_id: str,
) -> str:
    private_matches = tuple(
        binding
        for binding in session.private_state.entity_bindings
        if binding.entity_kind == entity_kind and binding.private_id == private_id
    )
    if len(private_matches) > 1:
        raise CatalogProviderError("authoritative entity has duplicate bindings")
    if not private_matches:
        return new_opaque_handle()
    handle = private_matches[0].public_handle
    public_matches = tuple(
        entity
        for entity in session.public_state.entity_handles
        if entity.entity_kind == entity_kind and entity.handle == handle
    )
    if len(public_matches) != 1:
        raise CatalogProviderError("private entity binding has no exact public handle")
    return handle


def _product_card(product: Product, interaction_handle: str) -> CatalogProductCard:
    prices = tuple(_variant_price(variant) for variant in product.variants)
    if not prices:
        raise CatalogProviderError("catalog product has no priced variants")
    currencies = {price.currency_code for price in prices}
    if len(currencies) != 1:
        raise CatalogProviderError("catalog product has inconsistent currencies")
    return CatalogProductCard(
        interaction_handle=interaction_handle,
        product_handle=product.handle,
        title=product.title,
        description=product.description,
        thumbnail_url=product.thumbnail,
        price=CatalogPrice(
            amount=min(price.amount for price in prices),
            currency_code=prices[0].currency_code,
        ),
        variant_count=len(product.variants),
    )


def _product_provider_value(
    session: RouteDeckSession,
    product: Product,
) -> CatalogProductProviderValue:
    product_private_id = product.id.get_secret_value()
    product_interaction_handle = _existing_or_new_handle(
        session,
        entity_kind="product",
        private_id=product_private_id,
    )
    variants: list[CatalogVariant] = []
    variant_bindings: list[CatalogPrivateBinding] = []
    for variant in product.variants:
        private_id = variant.id.get_secret_value()
        interaction_handle = _existing_or_new_handle(
            session,
            entity_kind="variant",
            private_id=private_id,
        )
        quantity = variant.inventory_quantity
        inventory_status = (
            InventoryStatus.UNKNOWN
            if quantity is None
            else (
                InventoryStatus.IN_STOCK
                if quantity > 0
                else InventoryStatus.OUT_OF_STOCK
            )
        )
        variants.append(
            CatalogVariant(
                interaction_handle=interaction_handle,
                title=variant.title,
                sku=variant.sku,
                price=_variant_price(variant),
                inventory_status=inventory_status,
                inventory_quantity=quantity,
                option_values=tuple(option.value for option in variant.options),
            )
        )
        variant_bindings.append(
            CatalogPrivateBinding(
                entity_kind="variant",
                interaction_handle=interaction_handle,
                private_id=SecretStr(private_id),
            )
        )
    if not variants:
        raise CatalogProviderError("catalog product has no variants")

    selected = _current_selected_variant(session, product.handle)
    if selected is not None and selected not in {
        variant.interaction_handle for variant in variants
    }:
        selected = None
    detail = CatalogProductDetail(
        interaction_handle=product_interaction_handle,
        product_handle=product.handle,
        title=product.title,
        description=product.description,
        thumbnail_url=product.thumbnail,
        image_urls=tuple(image.url for image in product.images),
        options=tuple(
            CatalogOption(
                title=option.title,
                values=tuple(value.value for value in option.values),
            )
            for option in product.options
        ),
        variants=tuple(variants),
        selected_variant_handle=selected,
    )
    return CatalogProductProviderValue(
        observation=CatalogProductObservation(product=detail),
        product_binding=CatalogPrivateBinding(
            entity_kind="product",
            interaction_handle=product_interaction_handle,
            private_id=SecretStr(product_private_id),
        ),
        variant_bindings=tuple(variant_bindings),
    )


def _variant_price(variant: ProductVariant) -> CatalogPrice:
    price = variant.calculated_price
    if price is None:
        raise CatalogProviderError("catalog variant has no calculated price")
    return CatalogPrice(
        amount=price.calculated_amount,
        currency_code=price.currency_code,
    )


def _current_selected_variant(
    session: RouteDeckSession,
    product_handle: str,
) -> str | None:
    surface = next(
        (
            candidate
            for candidate in session.public_state.surface_state
            if candidate.surface_id == PRODUCT_DETAIL.id
        ),
        None,
    )
    if surface is None:
        return None
    values = {value.name: value.value.to_python() for value in surface.values}
    observation = CatalogProductObservation.model_validate(values)
    if observation.product.product_handle != product_handle:
        return None
    return observation.product.selected_variant_handle


__all__ = [
    "CatalogProvider",
    "CatalogProviderError",
    "CatalogRouteKeyValidator",
    "CurrentCatalogProductProvider",
]
