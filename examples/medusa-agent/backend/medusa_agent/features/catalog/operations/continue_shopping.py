from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.ports.executor import ExecutionContext

from ....identifiers import MedusaOutcomeType
from ..feature import CONTINUE_SHOPPING


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
            outcome=MedusaOutcomeType.CONTINUED,
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
        )
