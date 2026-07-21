from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar, cast, get_type_hints

from ..contracts.operations import GuardRef, OperationRef, ProviderRef
from ..contracts.operations import OperationOutcome
from ..ports.executor import OperationHandler
from ..validation import RouteDeckValidationError
from .compiled import CompiledApplication

if TYPE_CHECKING:
    from ..supervision.guards import (
        GuardDecision,
        GuardInvocationContext,
        ProviderInvocationContext,
        ProviderResult,
    )


class ContextProviderHandler(Protocol):
    async def __call__(
        self,
        context: ProviderInvocationContext,
    ) -> ProviderResult: ...


class GuardHandler(Protocol):
    async def __call__(
        self,
        context: GuardInvocationContext,
    ) -> GuardDecision: ...


_BindingKey = TypeVar("_BindingKey")
_BindingValue = TypeVar("_BindingValue")


@dataclass(frozen=True)
class FeatureBindings:
    handlers: Mapping[OperationRef, OperationHandler]
    providers: Mapping[ProviderRef, ContextProviderHandler]
    guards: Mapping[GuardRef, GuardHandler]

    @classmethod
    def merge(cls, *parts: FeatureBindings) -> FeatureBindings:
        """Compose feature bindings while rejecting ambiguous ownership."""

        handlers: dict[OperationRef, OperationHandler] = {}
        providers: dict[ProviderRef, ContextProviderHandler] = {}
        guards: dict[GuardRef, GuardHandler] = {}
        for part in parts:
            _merge_binding_map("handler", handlers, part.handlers)
            _merge_binding_map("provider", providers, part.providers)
            _merge_binding_map("guard", guards, part.guards)
        return cls(handlers=handlers, providers=providers, guards=guards)


@dataclass(frozen=True)
class BoundApplication:
    app: CompiledApplication
    bindings: FeatureBindings


def bind_app(
    app: CompiledApplication,
    bindings: FeatureBindings,
) -> BoundApplication:
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
    return BoundApplication(app=app, bindings=bindings)


def _require_exact_refs(
    *, kind: str, expected: set[object], actual: set[object]
) -> None:
    missing = sorted(str(ref) for ref in expected - actual)
    extra = sorted(str(ref) for ref in actual - expected)
    if missing or extra:
        raise RouteDeckValidationError(
            f"Invalid {kind} bindings: missing={missing!r}, extra={extra!r}"
        )


def _merge_binding_map(
    kind: str,
    destination: dict[_BindingKey, _BindingValue],
    source: Mapping[_BindingKey, _BindingValue],
) -> None:
    duplicates = sorted(str(ref) for ref in destination.keys() & source.keys())
    if duplicates:
        raise RouteDeckValidationError(
            f"Duplicate {kind} bindings: refs={duplicates!r}"
        )
    destination.update(source)


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
    "BoundApplication",
    "ContextProviderHandler",
    "FeatureBindings",
    "GuardHandler",
    "OperationHandler",
    "bind_app",
]
