from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.ports.executor import ExecutionContext

from ..feature import CATALOG_LIST
from .common import collection_outcome, collection_value


class ListCatalogHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        if arguments:
            raise ValueError(f"{CATALOG_LIST.id} accepts no arguments")
        return collection_outcome(collection_value(context), outcome="listed")
