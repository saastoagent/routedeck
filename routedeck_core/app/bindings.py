from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ..contracts.operations import GuardRef, OperationRef, ProviderRef
from ..validation import RouteDeckValidationError
from .compiled import CompiledRouteDeckApp


class OperationHandler(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> object: ...


class ContextProvider(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> object: ...


class Guard(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> object: ...


@dataclass(frozen=True)
class FeatureBindings:
    handlers: Mapping[OperationRef, OperationHandler]
    providers: Mapping[ProviderRef, ContextProvider]
    guards: Mapping[GuardRef, Guard]


@dataclass(frozen=True)
class BoundRouteDeckApp:
    app: CompiledRouteDeckApp
    bindings: FeatureBindings


def bind_app(
    app: CompiledRouteDeckApp,
    bindings: FeatureBindings,
) -> BoundRouteDeckApp:
    _require_exact_refs(
        kind="handler",
        expected={operation.ref for operation in app.operations.values()},
        actual=set(bindings.handlers),
    )
    _require_exact_refs(
        kind="provider",
        expected={provider.ref for provider in app.providers.values()},
        actual=set(bindings.providers),
    )
    _require_exact_refs(
        kind="guard",
        expected={guard.ref for guard in app.guards.values()},
        actual=set(bindings.guards),
    )
    return BoundRouteDeckApp(app=app, bindings=bindings)


def _require_exact_refs(*, kind: str, expected: set[object], actual: set[object]) -> None:
    missing = sorted(str(ref) for ref in expected - actual)
    extra = sorted(str(ref) for ref in actual - expected)
    if missing or extra:
        raise RouteDeckValidationError(
            f"Invalid {kind} bindings: missing={missing!r}, extra={extra!r}"
        )


__all__ = [
    "BoundRouteDeckApp",
    "ContextProvider",
    "FeatureBindings",
    "Guard",
    "OperationHandler",
    "bind_app",
]
