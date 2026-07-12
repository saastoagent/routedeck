from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
    ExactRouteParameter,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import (
    FrozenJson,
    FrozenJsonObject,
    PublicEntityHandle,
    PublicValue,
)
from routedeck_core.ports.executor import ExecutionContext
from routedeck_core.supervision.guards import (
    GuardDecision,
    GuardInvocationContext,
)

from .feature import (
    CATALOG_LIST,
    CATALOG_PRODUCTS_PROVIDER,
    CATALOG_PRODUCT_PROVIDER,
    CATALOG_SEARCH,
    CATALOG_VARIANTS_PROVIDER,
    CONTINUE_SHOPPING,
    OPEN_PRODUCT,
    OPEN_PRODUCT_BY_ROUTE,
    PRODUCT_DETAIL,
    PRODUCT_GRID,
    SELECT_VARIANT,
)
from .models import (
    CatalogCollectionProviderValue,
    CatalogPrivateBinding,
    CatalogProductDetail,
    CatalogProductProviderValue,
    CatalogProductObservation,
    CatalogSelectionObservation,
)


class ListCatalogHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        if arguments:
            raise ValueError(f"{CATALOG_LIST.id} accepts no arguments")
        value = _collection_value(context)
        return _collection_outcome(value, outcome="listed")


class SearchCatalogHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        query = arguments.get("query")
        if not isinstance(query, str) or not query or set(arguments) != {"query"}:
            raise ValueError(f"{CATALOG_SEARCH.id} requires one exact query")
        value = _collection_value(context)
        if value.observation.query != query:
            raise ValueError("catalog search provider query does not match the request")
        return _collection_outcome(value, outcome="searched")


class OpenProductHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        interaction_handle = arguments.get("product_ref")
        if not isinstance(interaction_handle, str) or set(arguments) != {
            "product_ref"
        }:
            raise ValueError(
                f"{OPEN_PRODUCT.id} requires one product interaction handle"
            )
        value = CatalogProductProviderValue.model_validate(
            context.provider_values.to_dict()[CATALOG_PRODUCT_PROVIDER.id]
        )
        detail = value.observation.product
        if detail.interaction_handle != interaction_handle:
            raise ValueError("catalog detail does not match the selected product")

        return _open_product_outcome(value)


class OpenProductByRouteHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        product_handle = arguments.get("product_handle")
        if (
            not isinstance(product_handle, str)
            or not product_handle
            or set(arguments) != {"product_handle"}
        ):
            raise ValueError(
                f"{OPEN_PRODUCT_BY_ROUTE.id} requires one exact public product handle"
            )
        value = CatalogProductProviderValue.model_validate(
            context.provider_values.to_dict()[CATALOG_PRODUCT_PROVIDER.id]
        )
        if value.observation.product.product_handle != product_handle:
            raise ValueError(
                "catalog detail does not match the requested product route"
            )
        return _open_product_outcome(value)


def _open_product_outcome(value: CatalogProductProviderValue) -> OperationOutcome:
    detail = value.observation.product
    product_effect = EntityKindEffects(
        entity_kind="product",
        bindings=(
            _binding_effect(
                value.product_binding,
                public=_product_entity(detail),
                allowed_operation_ids=(),
            ),
        ),
    )
    variant_effect = EntityKindEffects(
        entity_kind="variant",
        bindings=tuple(
            _binding_effect(
                binding,
                public=_variant_entity(detail, binding.interaction_handle),
                allowed_operation_ids=(SELECT_VARIANT.id, "cart.add_item"),
            )
            for binding in value.variant_bindings
        ),
    )
    observation = value.observation.model_dump(mode="json", exclude_none=True)
    return OperationOutcome(
        outcome="opened",
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        observation=FrozenJsonObject(observation),
        effects=SessionEffects(
            replace_entities=(product_effect, variant_effect),
            surface_updates=(
                PublicSurfaceEffect(
                    surface_id=PRODUCT_DETAIL.id,
                    values=_public_values(observation),
                ),
            ),
            route_params=(
                ExactRouteParameter(
                    name="product_handle",
                    value=detail.product_handle,
                ),
            ),
        ),
    )


class SelectVariantHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        interaction_handle = arguments.get("variant_ref")
        if not isinstance(interaction_handle, str) or set(arguments) != {"variant_ref"}:
            raise ValueError(f"{SELECT_VARIANT.id} requires one variant reference")
        current = CatalogProductObservation.model_validate(
            context.provider_values.to_dict()[CATALOG_VARIANTS_PROVIDER.id]
        )
        if interaction_handle not in {
            variant.interaction_handle for variant in current.product.variants
        }:
            raise ValueError(
                "selected variant is not present in current product detail"
            )
        selected = current.product.model_copy(
            update={"selected_variant_handle": interaction_handle}
        )
        projected = CatalogProductObservation(product=selected).model_dump(
            mode="json", exclude_none=True
        )
        observation = CatalogSelectionObservation(
            product_handle=selected.product_handle,
            variant_handle=interaction_handle,
        )
        return OperationOutcome(
            outcome="selected",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            observation=FrozenJsonObject(observation.model_dump(mode="json")),
            effects=SessionEffects(
                surface_updates=(
                    PublicSurfaceEffect(
                        surface_id=PRODUCT_DETAIL.id,
                        values=_public_values(projected),
                    ),
                )
            ),
        )


class ContinueShoppingHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        del context
        if arguments:
            raise ValueError(f"{CONTINUE_SHOPPING.id} accepts no arguments")
        return OperationOutcome(
            outcome="continued",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        )


class PublicProductGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        product_entities = tuple(
            entity
            for entity in context.resolved_entities
            if entity.argument_name == "product_ref"
            and entity.entity_kind == "product"
        )
        if len(product_entities) == 1:
            provider = context.provider_values.to_dict().get(
                CATALOG_PRODUCT_PROVIDER.id
            )
            if isinstance(provider, dict):
                detail = CatalogProductProviderValue.model_validate(provider)
                requested = context.request.arguments.to_dict().get("product_ref")
                if detail.observation.product.interaction_handle == requested:
                    return GuardDecision.allowed_result()
        return GuardDecision.blocked(
            _guard_failure(
                context,
                code="product_not_current",
                message="That product is no longer available in this catalog view.",
            )
        )


class VariantAllowedGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        variant_entities = tuple(
            entity
            for entity in context.resolved_entities
            if entity.argument_name == "variant_ref" and entity.entity_kind == "variant"
        )
        provider = context.provider_values.to_dict().get(CATALOG_VARIANTS_PROVIDER.id)
        if len(variant_entities) == 1 and isinstance(provider, dict):
            detail = CatalogProductObservation.model_validate(provider)
            requested = context.request.arguments.to_dict().get("variant_ref")
            if requested in {
                variant.interaction_handle for variant in detail.product.variants
            }:
                return GuardDecision.allowed_result()
        return GuardDecision.blocked(
            _guard_failure(
                context,
                code="variant_not_allowed",
                message="That variant is no longer available for this product.",
            )
        )


def _collection_value(context: ExecutionContext) -> CatalogCollectionProviderValue:
    return CatalogCollectionProviderValue.model_validate(
        context.provider_values.to_dict()[CATALOG_PRODUCTS_PROVIDER.id]
    )


def _collection_outcome(
    value: CatalogCollectionProviderValue,
    *,
    outcome: str,
) -> OperationOutcome:
    observation = value.observation.model_dump(mode="json", exclude_none=True)
    cards = {
        product.interaction_handle: product for product in value.observation.products
    }
    entities = EntityKindEffects(
        entity_kind="product",
        bindings=tuple(
            _binding_effect(
                binding,
                public=_product_card_entity(cards[binding.interaction_handle]),
                allowed_operation_ids=(OPEN_PRODUCT.id,),
            )
            for binding in value.bindings
        ),
    )
    return OperationOutcome(
        outcome=outcome,
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        observation=FrozenJsonObject(observation),
        effects=SessionEffects(
            replace_entities=(entities,),
            surface_updates=(
                PublicSurfaceEffect(
                    surface_id=PRODUCT_GRID.id,
                    values=_public_values(observation),
                ),
            ),
        ),
    )


def _binding_effect(
    binding: CatalogPrivateBinding,
    *,
    public: PublicEntityHandle,
    allowed_operation_ids: tuple[str, ...],
) -> EntityBindingEffect:
    if public.handle != binding.interaction_handle:
        raise ValueError("public and private catalog bindings must match")
    return EntityBindingEffect(
        public=public,
        private_id=binding.private_id,
        allowed_operation_ids=allowed_operation_ids,
    )


def _product_card_entity(product: Any) -> PublicEntityHandle:
    return PublicEntityHandle(
        entity_kind="product",
        handle=product.interaction_handle,
        values=(
            PublicValue(
                name="product_handle",
                value=FrozenJson(product.product_handle),
            ),
            PublicValue(name="title", value=FrozenJson(product.title)),
        ),
    )


def _product_entity(product: CatalogProductDetail) -> PublicEntityHandle:
    return PublicEntityHandle(
        entity_kind="product",
        handle=product.interaction_handle,
        values=(
            PublicValue(
                name="product_handle",
                value=FrozenJson(product.product_handle),
            ),
            PublicValue(name="title", value=FrozenJson(product.title)),
        ),
    )


def _variant_entity(
    product: CatalogProductDetail,
    interaction_handle: str,
) -> PublicEntityHandle:
    variant = next(
        candidate
        for candidate in product.variants
        if candidate.interaction_handle == interaction_handle
    )
    values = [
        PublicValue(name="title", value=FrozenJson(variant.title)),
        PublicValue(
            name="product_handle",
            value=FrozenJson(product.product_handle),
        ),
    ]
    if variant.sku is not None:
        values.append(PublicValue(name="sku", value=FrozenJson(variant.sku)))
    return PublicEntityHandle(
        entity_kind="variant",
        handle=interaction_handle,
        values=tuple(values),
    )


def _public_values(values: Mapping[str, Any]) -> tuple[PublicValue, ...]:
    return tuple(
        PublicValue(name=name, value=FrozenJson(value))
        for name, value in values.items()
    )


def _guard_failure(
    context: GuardInvocationContext,
    *,
    code: str,
    message: str,
) -> RouteDeckFailure:
    return RouteDeckFailure(
        kind=FailureKind.GUARD,
        code=code,
        phase="guard",
        correlation_id=context.attempt_id,
        operation_id=context.request.operation_id,
        request_id=context.request.request_id,
        public_message=message,
    )


__all__ = [
    "ContinueShoppingHandler",
    "ListCatalogHandler",
    "OpenProductHandler",
    "OpenProductByRouteHandler",
    "PublicProductGuard",
    "SearchCatalogHandler",
    "SelectVariantHandler",
    "VariantAllowedGuard",
]
