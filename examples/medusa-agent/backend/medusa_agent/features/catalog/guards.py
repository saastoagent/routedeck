from __future__ import annotations

from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.supervision.guards import GuardDecision, GuardInvocationContext

from .declarations import CATALOG_PRODUCT_PROVIDER, CATALOG_VARIANTS_PROVIDER
from .models import (
    CatalogProductObservation,
    CatalogProductProviderValue,
)


class PublicProductGuard:
    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        product_entities = tuple(
            entity
            for entity in context.resolved_entities
            if entity.argument_name == "product_ref" and entity.entity_kind == "product"
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


__all__ = ["PublicProductGuard", "VariantAllowedGuard"]
