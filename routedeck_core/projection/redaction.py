from __future__ import annotations

from collections.abc import Iterable, Mapping

from jsonschema.validators import validator_for

from ..contracts.projection import (
    ClassifiedValue,
    DataClassification,
    PublicValue,
)
from ..validation import RouteDeckValidationError


def project_public_values(
    values: Iterable[ClassifiedValue],
    *,
    schema: Mapping[str, object],
) -> tuple[PublicValue, ...]:
    """Project explicitly public values; all other classifications are denied."""

    projected = tuple(
        PublicValue(name=value.name, value=value.value)
        for value in values
        if value.classification is DataClassification.PUBLIC
    )
    candidate = {value.name: value.value.to_python() for value in projected}
    if not schema:
        if candidate:
            raise RouteDeckValidationError(
                "Surface public props are not declared by schema"
            )
        return projected
    validator_type = validator_for(schema)
    if not validator_type(schema).is_valid(candidate):
        raise RouteDeckValidationError(
            "Surface public props do not satisfy the declared schema"
        )
    return projected


__all__ = ["project_public_values"]
