from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_serializer

from ..contracts.application import CompiledApplicationSpec
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.operations import (
    GuardSpec,
    OperationSpec,
    ProviderSpec,
    SafetyClass,
)
from ..contracts.surfaces import SurfaceSpec
from .feature import ApplicationSpec

if TYPE_CHECKING:
    from ..navigation.routes import CompiledRoutes


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FrontendSurfaceSlots(_FrozenContract):
    active: str
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


class FrontendContract(_FrozenContract):
    name: str
    entry_node_id: str
    nodes: Mapping[str, FrontendNodeContract]
    transitions: tuple[FrontendTransitionContract, ...]
    surfaces: Mapping[str, SurfaceSpec]

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
                surface_id: surface.model_dump(
                    mode="json",
                    exclude={"private_form_binding"},
                )
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
class CompiledRouteDeckApp:
    source_spec: ApplicationSpec
    spec: CompiledApplicationSpec
    operations: Mapping[str, OperationSpec]
    providers: Mapping[str, ProviderSpec]
    guards: Mapping[str, GuardSpec]
    surfaces: Mapping[str, SurfaceSpec]
    routes: CompiledRoutes
    frontend_contract: FrontendContract
    executable_test_paths: tuple[ExecutableTestPath, ...]

    def contract_documents(self) -> dict[str, str]:
        documents = {
            "compiled-navgraph.json": self.spec.model_dump(mode="json"),
            "frontend-contract.json": self.frontend_contract.model_dump(mode="json"),
            "contract-schema.json": {
                "application_spec": ApplicationSpec.model_json_schema(),
                "compiled_application": CompiledApplicationSpec.model_json_schema(),
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
    "CompiledRouteDeckApp",
    "ExecutableTestPath",
    "FrontendContract",
    "FrontendNodeContract",
    "FrontendSurfaceSlots",
    "FrontendTransitionContract",
]
