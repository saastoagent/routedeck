from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from routedeck_core.app import CompiledApplication
from routedeck_core.app.compiled import FrontendContract
from routedeck_core.contracts.events import PublicRouteDeckEvent
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.projection import PublicProjection
from routedeck_fastapi.conversation_projection import (
    ConversationHistoryEnvelope,
    PublicConversationTurn,
)
from routedeck_fastapi.conversation_runs import (
    ConversationRunEnvelope,
    ConversationRunFailurePayload,
    ConversationRunReviewPayload,
    ConversationRunSnapshotPayload,
)
from routedeck_fastapi.conversation_sse import (
    ConversationAssistantDeltaPayload,
    ConversationAssistantEndPayload,
    ConversationAssistantResetPayload,
    ConversationChatErrorPayload,
    ConversationReviewRequiredPayload,
    ConversationSnapshotPayload,
    ConversationStreamEndPayload,
    ConversationStreamStartPayload,
    ConversationUserMessagePayload,
)
from routedeck_fastapi.contracts import (
    DispatchRequest,
    PrivateFormWriteRequest,
    ReviewRequest,
)
from routedeck_fastapi.responses import PublicOperationResult
from routedeck_fastapi.sse import StreamResetPayload


class _TransportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicProjectionResponse(PublicProjection):
    """Projection shape emitted by the FastAPI transport."""

    graph_node: str | None = None


class SessionEnvelope(_TransportPayload):
    projection: PublicProjectionResponse


class FrontendContractEnvelope(_TransportPayload):
    frontend_contract: FrontendContract


class FailureEnvelope(_TransportPayload):
    failure: RouteDeckFailure


class PrivateFormSnapshot(_TransportPayload):
    form_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    complete: bool
    session_version: int = Field(ge=0)
    value: dict[str, Any]


class PrivateFormSaved(_TransportPayload):
    form_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    complete: bool
    session_version: int = Field(ge=0)
    projection_version: int = Field(ge=0)


class InspectionPayload(_TransportPayload):
    current_node: str
    reachable_nodes: list[str]
    legal_operations: list[dict[str, Any]]
    blocked_operations: list[dict[str, Any]]
    guard_explanations: list[str]
    capabilities: list[dict[str, Any]]
    surfaces: dict[str, Any]
    route_traces: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    agent_context: dict[str, Any] | None


class RouteDeckTransportContracts(BaseModel):
    """Schema catalog consumed by the headless TypeScript package."""

    model_config = ConfigDict(extra="forbid")

    public_projection: PublicProjection
    event: PublicRouteDeckEvent
    failure: RouteDeckFailure
    operation_result: PublicOperationResult
    frontend_contract: FrontendContract
    dispatch_request: DispatchRequest
    review_request: ReviewRequest
    private_form_write_request: PrivateFormWriteRequest
    session_envelope: SessionEnvelope
    frontend_contract_envelope: FrontendContractEnvelope
    failure_envelope: FailureEnvelope
    private_form_snapshot: PrivateFormSnapshot
    private_form_saved: PrivateFormSaved
    inspection: InspectionPayload
    conversation_history: ConversationHistoryEnvelope
    conversation_turn: PublicConversationTurn
    conversation_stream_start: ConversationStreamStartPayload
    conversation_snapshot: ConversationSnapshotPayload
    conversation_user_message: ConversationUserMessagePayload
    conversation_assistant_delta: ConversationAssistantDeltaPayload
    conversation_assistant_reset: ConversationAssistantResetPayload
    conversation_assistant_end: ConversationAssistantEndPayload
    conversation_review_required: ConversationReviewRequiredPayload
    conversation_chat_error: ConversationChatErrorPayload
    conversation_stream_end: ConversationStreamEndPayload
    conversation_run_envelope: ConversationRunEnvelope
    conversation_run_snapshot: ConversationRunSnapshotPayload
    conversation_run_failure: ConversationRunFailurePayload
    conversation_run_review: ConversationRunReviewPayload
    stream_reset: StreamResetPayload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export deterministic contracts from a compiled RouteDeck app."
    )
    parser.add_argument(
        "--app-factory",
        help="Ordinary import target in module:function form.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--schema-output",
        type=Path,
        help="Write the generic RouteDeck transport schema catalog.",
    )
    parser.add_argument(
        "--runtime-output",
        type=Path,
        help="Write generated TypeScript runtime object descriptors.",
    )
    return parser.parse_args()


def _load_factory(target: str) -> Callable[[], CompiledApplication]:
    module_name, separator, attribute_name = target.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("--app-factory must use module:function form")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute_name)
    if not callable(factory):
        raise TypeError(f"App factory is not callable: {target}")
    return factory


def export_contracts(
    factory: Callable[[], CompiledApplication],
    output: Path,
) -> tuple[Path, ...]:
    app = factory()
    if not isinstance(app, CompiledApplication):
        raise TypeError("App factory must return CompiledApplication")
    documents: Mapping[str, str] = app.contract_documents()
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in sorted(documents):
        destination = output / name
        destination.write_text(documents[name], encoding="utf-8", newline="\n")
        written.append(destination)
    return tuple(written)


def transport_schema() -> dict[str, Any]:
    return RouteDeckTransportContracts.model_json_schema(
        ref_template="#/$defs/{model}",
    )


def export_transport_schema(output: Path) -> Path:
    schema = transport_schema()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            schema,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def _object_descriptors(schema: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    _reject_unsupported_all_of(schema)
    candidates = {
        "RouteDeckTransportContracts": schema,
        **schema.get("$defs", {}),
    }
    descriptors: dict[str, dict[str, Any]] = {}
    for name, candidate in sorted(candidates.items()):
        if not isinstance(candidate, Mapping):
            continue
        if candidate.get("type") != "object":
            continue
        properties = candidate.get("properties", {})
        if not isinstance(properties, Mapping):
            continue
        required = frozenset(candidate.get("required", ()))
        property_names = sorted(str(property_name) for property_name in properties)
        descriptors[name] = {
            "required": sorted(required),
            "optional": [
                property_name
                for property_name in property_names
                if property_name not in required
            ],
            "additionalProperties": candidate.get("additionalProperties", True)
            is not False,
            "defaults": {
                property_name: properties[property_name]["default"]
                for property_name in property_names
                if isinstance(properties[property_name], Mapping)
                and "default" in properties[property_name]
            },
        }
    return dict(sorted(descriptors.items()))


def _reject_unsupported_all_of(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        if "allOf" in value:
            raise ValueError(
                f"Object descriptor generation does not support allOf at {path}"
            )
        for key, child in sorted(value.items(), key=lambda item: str(item[0])):
            _reject_unsupported_all_of(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_unsupported_all_of(child, f"{path}[{index}]")


def render_runtime_descriptors(schema: Mapping[str, Any]) -> str:
    descriptors = _object_descriptors(schema)
    lines = [
        "/* eslint-disable */",
        "/**",
        " * Generated from the RouteDeck Pydantic transport schema.",
        " * DO NOT MODIFY IT BY HAND. Run `pnpm contracts:generate`.",
        " */",
        "",
        "export interface GeneratedObjectDescriptor {",
        "  readonly required: readonly string[];",
        "  readonly optional: readonly string[];",
        "  readonly additionalProperties: boolean;",
        "  readonly defaults: Readonly<Record<string, unknown>>;",
        "}",
        "",
        "export const generatedObjectDescriptors = Object.freeze({",
    ]
    for name, descriptor in descriptors.items():
        required = json.dumps(descriptor["required"], ensure_ascii=False)
        optional = json.dumps(descriptor["optional"], ensure_ascii=False)
        additional = str(descriptor["additionalProperties"]).lower()
        defaults = json.dumps(
            descriptor["defaults"], ensure_ascii=False, sort_keys=True
        )
        lines.extend(
            [
                f"  {name}: Object.freeze({{",
                f"    required: Object.freeze({required}),",
                f"    optional: Object.freeze({optional}),",
                f"    additionalProperties: {additional},",
                f"    defaults: Object.freeze({defaults}),",
                "  }),",
            ]
        )
    lines.extend(
        [
            "}) satisfies Readonly<Record<string, GeneratedObjectDescriptor>>;",
            "",
        ]
    )
    return "\n".join(lines)


def export_runtime_descriptors(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_runtime_descriptors(transport_schema()),
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    args = _parse_args()
    if args.schema_output is not None:
        if args.app_factory is not None or args.output is not None:
            raise ValueError(
                "--schema-output cannot be combined with --app-factory or --output"
            )
        print(export_transport_schema(args.schema_output))
        if args.runtime_output is not None:
            print(export_runtime_descriptors(args.runtime_output))
        return 0
    if args.runtime_output is not None:
        raise ValueError("--runtime-output requires --schema-output")
    if args.app_factory is None or args.output is None:
        raise ValueError("--app-factory and --output are required together")
    written = export_contracts(_load_factory(args.app_factory), args.output)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
