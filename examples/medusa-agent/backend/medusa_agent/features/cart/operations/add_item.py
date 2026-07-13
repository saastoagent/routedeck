from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.handles import new_opaque_handle
from routedeck_core.ports.executor import ExecutionContext

from ....medusa.client.protocol import MedusaStoreClient
from ..feature import CART_ADD_ITEM
from ..models import EntityHandleFactory
from .common import current_cart, mutation_outcome, require_arguments, required_quantity


@dataclass(frozen=True)
class AddCartItemHandler:
    client: MedusaStoreClient
    new_entity_handle: EntityHandleFactory = new_opaque_handle

    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        require_arguments(
            arguments,
            expected=("variant_ref", "quantity"),
            operation_id=CART_ADD_ITEM.id,
        )
        current = current_cart(context)
        result = await self.client.add_line_item(
            current.private_cart_id,
            context.private_entity_id("variant_ref"),
            required_quantity(arguments),
        )
        return mutation_outcome(
            context=context,
            operation_id=CART_ADD_ITEM.id,
            outcome="added",
            result=result,
            current=current,
            new_entity_handle=self.new_entity_handle,
            project_surface=False,
            allow_line_mutations=False,
        )
