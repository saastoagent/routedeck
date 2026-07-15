from __future__ import annotations

from typing import TypeVar

from ..contracts.surfaces import SurfaceSlotsSpec, SurfaceSpec
from ..validation import RouteDeckValidationError
from .feature import ApplicationSpec


ContractT = TypeVar("ContractT")


def _validate_feature_namespaces(source_spec: ApplicationSpec) -> None:
    namespaces = [feature.namespace for feature in source_spec.features]
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


def _all_surfaces(slots: SurfaceSlotsSpec) -> tuple[SurfaceSpec, ...]:
    return slots.declared_surfaces()
