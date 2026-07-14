from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from routedeck_core.contracts.operations import OperationOutcome
from routedeck_core.ports.executor import ExecutionContext

from ....identifiers import MedusaOutcomeType
from ..feature import CATALOG_SEARCH
from .common import collection_outcome, collection_value


class SearchCatalogHandler:
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        query = arguments.get("query")
        if not isinstance(query, str) or not query or set(arguments) != {"query"}:
            raise ValueError(f"{CATALOG_SEARCH.id} requires one exact query")
        value = collection_value(context)
        if value.observation.query != query:
            raise ValueError("catalog search provider query does not match the request")
        return collection_outcome(value, outcome=MedusaOutcomeType.SEARCHED)
