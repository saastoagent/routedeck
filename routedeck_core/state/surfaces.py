from __future__ import annotations

from ..app.compiled import CompiledApplication
from ..contracts.application import Node
from ..contracts.session import PublicSurfaceState
from ..contracts.surfaces import SurfaceLifecycle
from ..validation import RouteDeckValidationError


def validate_canonical_surface_state(
    app: CompiledApplication,
    surface_state: tuple[PublicSurfaceState, ...],
) -> None:
    """Require every stored surface ID to exist in the compiled global catalog."""

    surface_ids = tuple(state.surface_id for state in surface_state)
    if len(surface_ids) != len(set(surface_ids)):
        raise RouteDeckValidationError(
            "Session contains duplicate canonical surface state"
        )
    unknown = sorted(set(surface_ids) - set(app.surfaces))
    if unknown:
        raise RouteDeckValidationError(
            f"Session contains unknown canonical surface state: {unknown!r}"
        )


def surface_state_for_node(
    app: CompiledApplication,
    surface_state: tuple[PublicSurfaceState, ...],
    node: Node,
) -> tuple[PublicSurfaceState, ...]:
    """Retain stable state globally and ephemeral state only while declared."""

    validate_canonical_surface_state(app, surface_state)
    declared_surface_ids = {surface.id for surface in node.surfaces.declared_surfaces()}
    return tuple(
        state
        for state in surface_state
        if (
            app.surfaces[state.surface_id].lifecycle is SurfaceLifecycle.STABLE
            or state.surface_id in declared_surface_ids
        )
    )


__all__ = ["surface_state_for_node", "validate_canonical_surface_state"]
