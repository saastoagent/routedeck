from __future__ import annotations

from typing import TypeVar

from ..contracts.surfaces import SurfaceSlots, Surface
from ..validation import RouteDeckValidationError
from .feature import Application


ContractT = TypeVar("ContractT")


def _validate_feature_namespaces(application: Application) -> None:
    namespaces = [feature.namespace for feature in application.features]
    if len(namespaces) != len(set(namespaces)):
        raise RouteDeckValidationError("Feature namespaces must be unique")


def _register_canonical(
    kind: str,
    catalog: dict[str, ContractT],
    identifier: str,
    value: ContractT,
) -> None:
    existing = catalog.get(identifier)
    if existing is None:
        catalog[identifier] = value
        return
    if existing is not value:
        raise RouteDeckValidationError(
            f"Distinct {kind} definitions reuse id {identifier!r}"
        )


def _all_surfaces(slots: SurfaceSlots) -> tuple[Surface, ...]:
    return slots.declared_surfaces()
