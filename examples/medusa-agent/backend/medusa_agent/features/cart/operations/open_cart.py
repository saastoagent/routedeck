from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.ports.executor import ExecutionContext

from ..feature import CART_OPEN
from .common import cart_effects, current_cart, require_arguments


@dataclass(frozen=True)
class OpenCartHandler:
    """Navigate using the authoritative cart refresh already run by the provider."""

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        require_arguments(arguments, expected=(), operation_id=CART_OPEN.id)
        return OperationOutcome(
            outcome="opened",
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            effects=cart_effects(
                current_cart(context),
                project_surface=True,
                allow_line_mutations=True,
            ),
        )
