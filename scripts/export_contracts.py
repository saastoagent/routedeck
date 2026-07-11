from __future__ import annotations

import argparse
import importlib
from collections.abc import Callable, Mapping
from pathlib import Path

from routedeck_core.app import CompiledRouteDeckApp


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export deterministic contracts from a compiled RouteDeck app."
    )
    parser.add_argument(
        "--app-factory",
        required=True,
        help="Ordinary import target in module:function form.",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _load_factory(target: str) -> Callable[[], CompiledRouteDeckApp]:
    module_name, separator, attribute_name = target.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("--app-factory must use module:function form")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute_name)
    if not callable(factory):
        raise TypeError(f"App factory is not callable: {target}")
    return factory


def export_contracts(
    factory: Callable[[], CompiledRouteDeckApp],
    output: Path,
) -> tuple[Path, ...]:
    app = factory()
    if not isinstance(app, CompiledRouteDeckApp):
        raise TypeError("App factory must return CompiledRouteDeckApp")
    documents: Mapping[str, str] = app.contract_documents()
    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in sorted(documents):
        destination = output / name
        destination.write_text(documents[name], encoding="utf-8", newline="\n")
        written.append(destination)
    return tuple(written)


def main() -> int:
    args = _parse_args()
    written = export_contracts(_load_factory(args.app_factory), args.output)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
