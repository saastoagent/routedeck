from __future__ import annotations

from routedeck_core.contracts.failures import (
    FailureKind,
    FailureSafeDetails,
    RouteDeckFailure,
)
from routedeck_core.contracts.session import AttemptTerminalState
from routedeck_core.supervision.guards import GuardDecision, GuardInvocationContext

from ...medusa.client.models import MedusaClientFailureKind
from .declarations import (
    CART_ADD_ITEM,
    CART_CREATE,
    CART_CREATE_UNKNOWN_RECOVERY,
    CART_MUTATION_UNKNOWN_RECOVERY,
    CART_OPEN,
    CART_REMOVE_ITEM,
    CART_STATE_PROVIDER,
    CART_UPDATE_ITEM,
)
from .models import CartProviderContext, CartProviderState


_FAILURE_KINDS = {
    MedusaClientFailureKind.TRANSPORT: FailureKind.TRANSPORT,
    MedusaClientFailureKind.PROVIDER_PROTOCOL: FailureKind.PROVIDER_PROTOCOL,
    MedusaClientFailureKind.BUSINESS: FailureKind.BUSINESS,
}


class CartExistsGuard:
    """Require a successfully refreshed, real cart before cart use."""

    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        provider_values = context.provider_values.to_dict()
        cart_context = CartProviderContext.from_provider_values(
            provider_values[CART_STATE_PROVIDER.id]
        )
        if cart_context.state is CartProviderState.READY:
            cart = cart_context.cart
            if cart is None:
                raise TypeError("ready cart context is missing its cart snapshot")
            previous = context.session.operation
            attempt = previous.active_attempt if previous is not None else None
            mutation_ids = {
                CART_ADD_ITEM.id,
                CART_UPDATE_ITEM.id,
                CART_REMOVE_ITEM.id,
            }
            if (
                attempt is not None
                and attempt.operation_id in mutation_ids
                and attempt.terminal is AttemptTerminalState.EXTERNAL_OUTCOME_UNKNOWN
                and context.request.operation_id != CART_OPEN.id
            ):
                return GuardDecision.blocked(
                    _failure(
                        context,
                        kind=FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
                        code="cart_mutation_outcome_unknown",
                        phase="guard",
                        message=(
                            "The previous cart change is uncertain; reopen the cart "
                            "before changing it again."
                        ),
                        recovery_directive=CART_MUTATION_UNKNOWN_RECOVERY,
                    )
                )
            if context.request.operation_id in {
                CART_UPDATE_ITEM.id,
                CART_REMOVE_ITEM.id,
            }:
                resolved = tuple(
                    entity
                    for entity in context.resolved_entities
                    if entity.argument_name == "line_item_ref"
                    and entity.entity_kind == "line_item"
                )
                current_line_ids = {
                    binding.private_id for binding in cart.line_bindings
                }
                if (
                    len(resolved) != 1
                    or resolved[0].private_id.get_secret_value() not in current_line_ids
                ):
                    return GuardDecision.blocked(
                        _failure(
                            context,
                            kind=FailureKind.GUARD,
                            code="line_item_not_current",
                            phase="guard",
                            message="That line item is no longer in the current cart.",
                        )
                    )
            return GuardDecision.allowed_result()
        if cart_context.state is CartProviderState.MISSING:
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="cart_required",
                    phase="guard",
                    message="Create a cart before using cart operations.",
                )
            )
        if (
            cart_context.failure_kind is None
            or cart_context.delivery_phase is None
            or cart_context.failure_code is None
            or cart_context.public_message is None
        ):
            raise TypeError("failed cart refresh is missing typed failure evidence")
        return GuardDecision.blocked(
            _failure(
                context,
                kind=_FAILURE_KINDS[cart_context.failure_kind],
                code=cart_context.failure_code,
                phase="context_refresh",
                message=cart_context.public_message,
                safe_details=FailureSafeDetails(
                    provider="medusa",
                    provider_code=cart_context.failure_code,
                    delivery_phase=cart_context.delivery_phase.value,
                ),
            )
        )


class CartAbsentGuard:
    """Prevent duplicate creation, including after an uncertain write."""

    async def __call__(self, context: GuardInvocationContext) -> GuardDecision:
        operation_state = context.session.operation
        active_attempt = (
            operation_state.active_attempt if operation_state is not None else None
        )
        if (
            active_attempt is not None
            and active_attempt.operation_id == CART_CREATE.id
            and active_attempt.terminal is AttemptTerminalState.EXTERNAL_OUTCOME_UNKNOWN
        ):
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
                    code="cart_creation_outcome_unknown",
                    phase="guard",
                    message=(
                        "Cart creation may have reached the store; do not create "
                        "another cart in this session."
                    ),
                    recovery_directive=CART_CREATE_UNKNOWN_RECOVERY,
                )
            )

        cart_bindings = tuple(
            binding
            for binding in context.session.private_state.entity_bindings
            if binding.entity_kind == "cart"
        )
        if len(cart_bindings) == 1:
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.GUARD,
                    code="cart_already_exists",
                    phase="guard",
                    message="This buyer session already has a cart.",
                )
            )
        if len(cart_bindings) > 1:
            return GuardDecision.blocked(
                _failure(
                    context,
                    kind=FailureKind.STATE_CONFLICT,
                    code="cart_state_invalid",
                    phase="guard",
                    message="The cart state is inconsistent and cannot continue.",
                )
            )
        return GuardDecision.allowed_result()


def _failure(
    context: GuardInvocationContext,
    *,
    kind: FailureKind,
    code: str,
    phase: str,
    message: str,
    recovery_directive: str | None = None,
    safe_details: FailureSafeDetails | None = None,
) -> RouteDeckFailure:
    return RouteDeckFailure(
        kind=kind,
        code=code,
        phase=phase,
        correlation_id=context.attempt_id,
        operation_id=context.request.operation_id,
        request_id=context.request.request_id,
        public_message=message,
        recovery_directive=recovery_directive,
        safe_details=safe_details or FailureSafeDetails(),
    )


__all__ = ["CartAbsentGuard", "CartExistsGuard"]
