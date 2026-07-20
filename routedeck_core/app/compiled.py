from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_serializer

from ..contracts.agent import AgentPolicy
from ..contracts.application import CompiledGraph, Node
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.operations import (
    Guard,
    Operation,
    Provider,
    SafetyClass,
)
from ..contracts.projection import FrozenJsonObject
from ..contracts.surfaces import (
    SurfaceAffordance,
    SurfaceLifecycle,
    Surface,
)
from ..validation import RouteDeckValidationError
from .feature import Application

if TYPE_CHECKING:
    from ..navigation.routes import CompiledRoutes


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FrontendSurfaceSlots(_FrozenContract):
    active: str | None
    frame: tuple[str, ...] = ()
    peer: tuple[str, ...] = ()
    detail: tuple[str, ...] = ()
    form: tuple[str, ...] = ()
    review: tuple[str, ...] = ()
    status: tuple[str, ...] = ()
    error: tuple[str, ...] = ()
    diagnostic: tuple[str, ...] = ()


class FrontendNodeContract(_FrozenContract):
    id: str
    title: str
    route_template: str
    deep_link_policy: DeepLinkPolicy
    surfaces: FrontendSurfaceSlots
    operation_ids: tuple[str, ...]


class FrontendTransitionContract(_FrozenContract):
    source: str
    operation_id: str
    outcome: str
    target: str


class FrontendSurfaceContract(_FrozenContract):
    id: str
    component: str
    lifecycle: SurfaceLifecycle
    affordances: tuple[SurfaceAffordance, ...] = ()
    public_props_schema: FrozenJsonObject


class FrontendContract(_FrozenContract):
    name: str
    entry_node_id: str
    nodes: Mapping[str, FrontendNodeContract]
    transitions: tuple[FrontendTransitionContract, ...]
    surfaces: Mapping[str, FrontendSurfaceContract]

    @model_serializer(mode="plain")
    def _public_contract(self) -> dict[str, object]:
        return {
            "name": self.name,
            "entry_node_id": self.entry_node_id,
            "nodes": {
                node_id: node.model_dump(mode="json")
                for node_id, node in self.nodes.items()
            },
            "transitions": [
                transition.model_dump(mode="json") for transition in self.transitions
            ],
            "surfaces": {
                surface_id: surface.model_dump(mode="json")
                for surface_id, surface in self.surfaces.items()
            },
        }


class ExecutableTestPath(_FrozenContract):
    node_id: str | None = None
    source_node_id: str | None = None
    target_node_id: str | None = None
    operation_id: str | None = None
    outcome: str | None = None
    deep_link_policy: DeepLinkPolicy | None = None
    safety_class: SafetyClass | None = None
    branch: str | None = None
    recovery_directive: str | None = None


@dataclass(frozen=True)
class CompiledApplication:
    application: Application
    graph: CompiledGraph
    nodes: Mapping[str, Node]
    operations: Mapping[str, Operation]
    providers: Mapping[str, Provider]
    guards: Mapping[str, Guard]
    agent_policies: Mapping[str, AgentPolicy]
    surfaces: Mapping[str, Surface]
    routes: CompiledRoutes
    frontend_contract: FrontendContract
    executable_test_paths: tuple[ExecutableTestPath, ...]

    def __post_init__(self) -> None:
        graph_nodes = {node.id: node for node in self.graph.nodes}
        if set(self.nodes) != set(graph_nodes) or any(
            self.nodes[node_id] is not node
            for node_id, node in graph_nodes.items()
        ):
            raise RouteDeckValidationError(
                "Compiled node index must exactly match the compiled graph"
            )
        object.__setattr__(self, "nodes", MappingProxyType(dict(self.nodes)))

    def require_node(self, node_id: str) -> Node:
        try:
            return self.nodes[node_id]
        except KeyError as error:
            raise RouteDeckValidationError(
                f"Compiled application does not contain node {node_id!r}"
            ) from error

    def contract_documents(self) -> dict[str, str]:
        documents = {
            "compiled-navgraph.json": self.graph.model_dump(mode="json"),
            "frontend-contract.json": self.frontend_contract.model_dump(mode="json"),
            "contract-schema.json": {
                "application": Application.model_json_schema(),
                "compiled_graph": CompiledGraph.model_json_schema(),
                "frontend_contract": FrontendContract.model_json_schema(),
            },
            "executable-test-paths.json": [
                path.model_dump(mode="json") for path in self.executable_test_paths
            ],
        }
        return {
            name: json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
            for name, value in documents.items()
        }


__all__ = [
    "CompiledApplication",
    "ExecutableTestPath",
    "FrontendContract",
    "FrontendNodeContract",
    "FrontendSurfaceContract",
    "FrontendSurfaceSlots",
    "FrontendTransitionContract",
]
