from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr

from routedeck_core.contracts.effects import (
    EntityBindingEffect,
    EntityKindEffects,
    PublicSurfaceEffect,
    SessionEffects,
)
from routedeck_core.contracts.failures import (
    FailureKind,
    FailureSafeDetails,
    RouteDeckFailure,
)
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.projection import (
    FrozenJson,
    FrozenJsonObject,
    PublicEntityHandle,
    PublicValue,
)
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ...medusa.client.models import (
    CartResult,
    CreateCartRequest,
    CreateCartResult,
    MedusaClientFailure,
    MedusaClientFailureKind,
)
from ...medusa.client.protocol import MedusaStoreClient
from .feature import (
    BUYER_MARKET_PROVIDER,
    CART_ADD_ITEM,
    CART_CREATE,
    CART_CREATED_OUTCOME,
    CART_OPEN,
    CART_REMOVE_ITEM,
    CART_STATE_PROVIDER,
    CART_SUMMARY,
    CART_UPDATE_ITEM,
)
from .models import (
    CartProviderContext,
    CartProviderState,
    CartSnapshot,
    EntityHandleFactory,
    project_cart,
    snapshot_entity_handles,
)


_FAILURE_KINDS = {
    MedusaClientFailureKind.TRANSPORT: FailureKind.TRANSPORT,
    MedusaClientFailureKind.PROVIDER_PROTOCOL: FailureKind.PROVIDER_PROTOCOL,
    MedusaClientFailureKind.BUSINESS: FailureKind.BUSINESS,
}


@dataclass(frozen=True)
class CreateCartHandler:
    """Create exactly one cart through the journaled Store write boundary."""

    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        _require_arguments(arguments, expected=(), operation_id=CART_CREATE.id)
        market = _provider_mapping(context, BUYER_MARKET_PROVIDER.id)
        request = CreateCartRequest(
            region_id=_required_string(market, "region_id"),
            country_code=_required_string(market, "country_code"),
            sales_channel_id=_required_string(market, "sales_channel_id"),
        )
        result = await self.client.create_cart(request)
        if not isinstance(result, CreateCartResult):
            raise TypeError(
                "MedusaStoreClient.create_cart must return CreateCartResult"
            )
        if result.failure is not None:
            return _failure_outcome(
                context=context,
                operation_id=CART_CREATE.id,
                delivery_phase=result.delivery_phase,
                failure=result.failure,
            )
        cart = result.cart
        if cart is None:
            raise TypeError("Successful CreateCartResult is missing its cart")
        expected_currency = _required_string(market, "currency_code")
        if cart.currency_code != expected_currency:
            return _protocol_failure_outcome(
                context=context,
                operation_id=CART_CREATE.id,
                code="cart_currency_mismatch",
                message="The store created a cart for an unexpected currency.",
            )

        private_cart_id = cart.id.get_secret_value()
        public_cart_handle = self.new_entity_handle()
        effects = SessionEffects(
            replace_entities=(
                EntityKindEffects(
                    entity_kind="cart",
                    bindings=(
                        EntityBindingEffect(
                            public=PublicEntityHandle(
                                entity_kind="cart",
                                handle=public_cart_handle,
                                values=(
                                    PublicValue(
                                        name="currency_code",
                                        value=FrozenJson(cart.currency_code),
                                    ),
                                ),
                            ),
                            private_id=SecretStr(private_cart_id),
                        ),
                    ),
                ),
            ),
        )
        return OperationOutcome(
            outcome=CART_CREATED_OUTCOME,
            delivery_phase=result.delivery_phase,
            observation=FrozenJsonObject(
                {
                    "cart_id": private_cart_id,
                    "currency_code": cart.currency_code,
                }
            ),
            effects=effects,
        )


@dataclass(frozen=True)
class AddCartItemHandler:
    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        _require_arguments(
            arguments,
            expected=("variant_ref", "quantity"),
            operation_id=CART_ADD_ITEM.id,
        )
        quantity = _required_quantity(arguments)
        current = _current_cart(context)
        variant_id = context.private_entity_id("variant_ref")
        result = await self.client.add_line_item(
            current.private_cart_id,
            variant_id,
            quantity,
        )
        return _mutation_outcome(
            context=context,
            operation_id=CART_ADD_ITEM.id,
            outcome="added",
            result=result,
            current=current,
            new_entity_handle=self.new_entity_handle,
            project_surface=False,
            allow_line_mutations=False,
        )


@dataclass(frozen=True)
class OpenCartHandler:
    """Navigate using the authoritative cart refresh already run by the provider."""

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        _require_arguments(arguments, expected=(), operation_id=CART_OPEN.id)
        current = _current_cart(context)
        return OperationOutcome(
            outcome="opened",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            effects=_cart_effects(
                current,
                project_surface=True,
                allow_line_mutations=True,
            ),
        )


@dataclass(frozen=True)
class UpdateCartItemHandler:
    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        _require_arguments(
            arguments,
            expected=("line_item_ref", "quantity"),
            operation_id=CART_UPDATE_ITEM.id,
        )
        quantity = _required_quantity(arguments)
        current = _current_cart(context)
        line_id = context.private_entity_id("line_item_ref")
        result = await self.client.update_line_item(
            current.private_cart_id,
            line_id,
            quantity,
        )
        return _mutation_outcome(
            context=context,
            operation_id=CART_UPDATE_ITEM.id,
            outcome="updated",
            result=result,
            current=current,
            new_entity_handle=self.new_entity_handle,
            project_surface=True,
            allow_line_mutations=True,
        )


@dataclass(frozen=True)
class RemoveCartItemHandler:
    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        _require_arguments(
            arguments,
            expected=("line_item_ref",),
            operation_id=CART_REMOVE_ITEM.id,
        )
        current = _current_cart(context)
        line_id = context.private_entity_id("line_item_ref")
        result = await self.client.remove_line_item(current.private_cart_id, line_id)
        return _mutation_outcome(
            context=context,
            operation_id=CART_REMOVE_ITEM.id,
            outcome="removed",
            result=result,
            current=current,
            new_entity_handle=self.new_entity_handle,
            project_surface=True,
            allow_line_mutations=True,
        )


def _mutation_outcome(
    *,
    context: ExecutionContext,
    operation_id: str,
    outcome: str,
    result: CartResult,
    current: CartSnapshot,
    new_entity_handle: EntityHandleFactory,
    project_surface: bool,
    allow_line_mutations: bool,
) -> OperationOutcome:
    if not isinstance(result, CartResult):
        raise TypeError("Medusa cart mutations must return CartResult")
    if result.failure is not None:
        return _failure_outcome(
            context=context,
            operation_id=operation_id,
            delivery_phase=result.delivery_phase,
            failure=result.failure,
        )
    cart = result.value
    if cart is None:
        raise TypeError("Successful CartResult is missing its cart")
    if cart.id.get_secret_value() != current.private_cart_id:
        return _protocol_failure_outcome(
            context=context,
            operation_id=operation_id,
            code="cart_identity_mismatch",
            message="The store returned a different cart for this operation.",
        )
    refreshed = project_cart(
        cart,
        new_entity_handle=new_entity_handle,
        existing_handles=snapshot_entity_handles(current),
    )
    return OperationOutcome(
        outcome=outcome,
        delivery_phase=result.delivery_phase,
        effects=_cart_effects(
            refreshed,
            project_surface=project_surface,
            allow_line_mutations=allow_line_mutations,
        ),
    )


def _cart_effects(
    snapshot: CartSnapshot,
    *,
    project_surface: bool,
    allow_line_mutations: bool,
) -> SessionEffects:
    cart_binding = EntityBindingEffect(
        public=PublicEntityHandle(
            entity_kind="cart",
            handle=snapshot.public_cart_handle,
            values=(
                PublicValue(
                    name="currency_code",
                    value=FrozenJson(snapshot.projection.currency_code),
                ),
                PublicValue(name="total", value=FrozenJson(snapshot.projection.total)),
            ),
        ),
        private_id=SecretStr(snapshot.private_cart_id),
    )
    line_operation_ids = (
        (CART_UPDATE_ITEM.id, CART_REMOVE_ITEM.id) if allow_line_mutations else ()
    )
    line_bindings = tuple(
        EntityBindingEffect(
            public=PublicEntityHandle(
                entity_kind="line_item",
                handle=line.public_handle,
                values=_line_values(snapshot, line.public_handle),
            ),
            private_id=SecretStr(line.private_id),
            allowed_operation_ids=line_operation_ids,
        )
        for line in snapshot.line_bindings
    )
    surface_updates: tuple[PublicSurfaceEffect, ...] = ()
    if project_surface:
        surface_values = tuple(
            PublicValue(name=name, value=FrozenJson(value))
            for name, value in snapshot.projection.model_dump(
                mode="json", exclude_none=True
            ).items()
        )
        surface_updates = (
            PublicSurfaceEffect(
                surface_id=CART_SUMMARY.id,
                values=surface_values,
            ),
        )
    return SessionEffects(
        replace_entities=(
            EntityKindEffects(entity_kind="cart", bindings=(cart_binding,)),
            EntityKindEffects(entity_kind="line_item", bindings=line_bindings),
        ),
        surface_updates=surface_updates,
    )


def _line_values(
    snapshot: CartSnapshot,
    public_handle: str,
) -> tuple[PublicValue, ...]:
    line = next(
        item
        for item in snapshot.projection.items
        if item.line_item_ref == public_handle
    )
    return tuple(
        PublicValue(name=name, value=FrozenJson(value))
        for name, value in line.model_dump(mode="json", exclude_none=True).items()
        if name != "line_item_ref"
    )


def _current_cart(context: ExecutionContext) -> CartSnapshot:
    values = _provider_mapping(context, CART_STATE_PROVIDER.id)
    cart_context = CartProviderContext.from_provider_values(values)
    if cart_context.state is not CartProviderState.READY or cart_context.cart is None:
        raise RuntimeError("cart handler requires an allowed authoritative cart")
    return cart_context.cart


def _provider_mapping(
    context: ExecutionContext,
    provider_id: str,
) -> Mapping[str, Any]:
    values = context.provider_values.to_dict()
    provider_value = values.get(provider_id)
    if not isinstance(provider_value, dict):
        raise RuntimeError(f"missing typed provider value for {provider_id}")
    return provider_value


def _required_string(values: Mapping[str, Any], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_quantity(arguments: Mapping[str, Any]) -> int:
    quantity = arguments.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError("quantity must be a positive integer")
    return quantity


def _require_arguments(
    arguments: Mapping[str, Any],
    *,
    expected: tuple[str, ...],
    operation_id: str,
) -> None:
    if set(arguments) != set(expected):
        raise ValueError(
            f"{operation_id} requires exactly these arguments: {expected!r}"
        )


def _failure_outcome(
    *,
    context: ExecutionContext,
    operation_id: str,
    delivery_phase: DeliveryPhase,
    failure: MedusaClientFailure,
) -> OperationOutcome:
    return OperationOutcome(
        delivery_phase=delivery_phase,
        failure=RouteDeckFailure(
            kind=_FAILURE_KINDS[failure.kind],
            code=failure.code,
            phase="execute",
            correlation_id=context.attempt_id,
            operation_id=operation_id,
            request_id=context.request_id,
            public_message=failure.public_message,
            safe_details=FailureSafeDetails(
                provider="medusa",
                provider_code=failure.code,
                delivery_phase=delivery_phase.value,
            ),
        ),
    )


def _protocol_failure_outcome(
    *,
    context: ExecutionContext,
    operation_id: str,
    code: str,
    message: str,
) -> OperationOutcome:
    return _failure_outcome(
        context=context,
        operation_id=operation_id,
        delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        failure=MedusaClientFailure(
            kind=MedusaClientFailureKind.PROVIDER_PROTOCOL,
            code=code,
            public_message=message,
        ),
    )


__all__ = [
    "AddCartItemHandler",
    "CreateCartHandler",
    "OpenCartHandler",
    "RemoveCartItemHandler",
    "UpdateCartItemHandler",
]
