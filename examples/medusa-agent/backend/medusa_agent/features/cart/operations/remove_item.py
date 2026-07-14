from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ....identifiers import MedusaOutcomeType
from ....medusa.client.protocol import MedusaStoreClient
from ..feature import CART_REMOVE_ITEM
from ..models import EntityHandleFactory
from .common import current_cart, mutation_outcome, require_arguments


@dataclass(frozen=True)
class RemoveCartItemHandler:
    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        require_arguments(
            arguments,
            expected=("line_item_ref",),
            operation_id=CART_REMOVE_ITEM.id,
        )
        current = current_cart(context)
        result = await self.client.remove_line_item(
            current.private_cart_id,
            context.private_entity_id("line_item_ref"),
        )
        return mutation_outcome(
            context=context,
            operation_id=CART_REMOVE_ITEM.id,
            outcome=MedusaOutcomeType.REMOVED,
            result=result,
            current=current,
            new_entity_handle=self.new_entity_handle,
            project_surface=True,
            allow_line_mutations=True,
        )
