from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast, get_type_hints

from ..contracts.operations import GuardRef, OperationRef, ProviderRef
from ..contracts.operations import OperationOutcome
from ..ports.executor import OperationHandler
from ..validation import RouteDeckValidationError
from .compiled import CompiledRouteDeckApp

if TYPE_CHECKING:
    from ..supervision.guards import (
        GuardDecision,
        GuardInvocationContext,
        ProviderInvocationContext,
        ProviderResult,
    )


class ContextProvider(Protocol):
    async def __call__(
        self,
        context: ProviderInvocationContext,
    ) -> ProviderResult: ...


class Guard(Protocol):
    async def __call__(
        self,
        context: GuardInvocationContext,
    ) -> GuardDecision: ...


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
    _require_async_bindings(
        kind="handler",
        bindings=bindings.handlers.values(),
        parameter_names=("arguments", "context"),
        return_type=OperationOutcome,
    )
    _require_async_bindings(
        kind="provider",
        bindings=bindings.providers.values(),
        parameter_names=("context",),
    )
    _require_async_bindings(
        kind="guard",
        bindings=bindings.guards.values(),
        parameter_names=("context",),
    )
    return BoundRouteDeckApp(app=app, bindings=bindings)


def _require_exact_refs(
    *, kind: str, expected: set[object], actual: set[object]
) -> None:
    missing = sorted(str(ref) for ref in expected - actual)
    extra = sorted(str(ref) for ref in actual - expected)
    if missing or extra:
        raise RouteDeckValidationError(
            f"Invalid {kind} bindings: missing={missing!r}, extra={extra!r}"
        )


def _require_async_bindings(
    *,
    kind: str,
    bindings: Iterable[object],
    parameter_names: tuple[str, ...],
    return_type: type[object] | None = None,
) -> None:
    for binding in bindings:
        candidate = (
            binding
            if inspect.isfunction(binding) or inspect.ismethod(binding)
            else getattr(binding, "__call__", None)
        )
        if candidate is None or not callable(candidate):
            raise RouteDeckValidationError(
                f"Invalid {kind} binding: implementation must be async"
            )
        target = cast(Callable[..., object], candidate)
        if not inspect.iscoroutinefunction(target):
            raise RouteDeckValidationError(
                f"Invalid {kind} binding: implementation must be async"
            )
        parameters = tuple(inspect.signature(target).parameters.values())
        if tuple(parameter.name for parameter in parameters) != parameter_names or any(
            parameter.kind is not inspect.Parameter.POSITIONAL_OR_KEYWORD
            or parameter.default is not inspect.Parameter.empty
            for parameter in parameters
        ):
            raise RouteDeckValidationError(
                f"Invalid {kind} binding signature: expected {parameter_names!r}"
            )
        if return_type is not None:
            try:
                actual_return = get_type_hints(target).get("return")
            except (NameError, TypeError) as error:
                raise RouteDeckValidationError(
                    f"Invalid {kind} binding return annotation"
                ) from error
            if actual_return is not return_type:
                raise RouteDeckValidationError(
                    f"Invalid {kind} binding return: expected {return_type.__name__}"
                )


__all__ = [
    "BoundRouteDeckApp",
    "ContextProvider",
    "FeatureBindings",
    "Guard",
    "OperationHandler",
    "bind_app",
]
