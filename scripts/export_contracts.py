from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from routedeck_core.app import CompiledApplication
from routedeck_core.app.compiled import FrontendContract
from routedeck_core.contracts.events import PublicRouteDeckEvent
from routedeck_core.contracts.failures import RouteDeckFailure
from routedeck_core.contracts.operations import OperationResult
from routedeck_core.contracts.projection import PublicProjection
from routedeck_fastapi.router import (
    DispatchRequest,
    PrivateFormWriteRequest,
    ReviewRequest,
)


class RouteDeckTransportContracts(BaseModel):
    """Schema catalog consumed by the headless TypeScript package."""

    model_config = ConfigDict(extra="forbid")

    public_projection: PublicProjection
    event: PublicRouteDeckEvent
    failure: RouteDeckFailure
    operation_result: OperationResult
    frontend_contract: FrontendContract
    dispatch_request: DispatchRequest
    review_request: ReviewRequest
    private_form_write_request: PrivateFormWriteRequest


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


def export_transport_schema(output: Path) -> Path:
    schema = RouteDeckTransportContracts.model_json_schema(
        ref_template="#/$defs/{model}",
    )
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


def main() -> int:
    args = _parse_args()
    if args.schema_output is not None:
        if args.app_factory is not None or args.output is not None:
            raise ValueError(
                "--schema-output cannot be combined with --app-factory or --output"
            )
        print(export_transport_schema(args.schema_output))
        return 0
    if args.app_factory is None or args.output is None:
        raise ValueError("--app-factory and --output are required together")
    written = export_contracts(_load_factory(args.app_factory), args.output)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
