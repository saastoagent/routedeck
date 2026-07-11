from __future__ import annotations

from dataclasses import dataclass

from ..contracts.session import Location
from ..validation import RouteDeckValidationError


@dataclass(frozen=True)
class NavigationHistory:
    current: Location
    back_stack: tuple[Location, ...]
    forward_stack: tuple[Location, ...]


def enter_location(
    *,
    current: Location,
    back_stack: tuple[Location, ...],
    location: Location,
) -> NavigationHistory:
    if location == current:
        return NavigationHistory(
            current=current,
            back_stack=back_stack,
            forward_stack=(),
        )
    return NavigationHistory(
        current=location,
        back_stack=(*back_stack, current),
        forward_stack=(),
    )


def move_back(
    *,
    current: Location,
    back_stack: tuple[Location, ...],
    forward_stack: tuple[Location, ...],
) -> NavigationHistory:
    if not back_stack:
        raise RouteDeckValidationError("Back navigation is not available")
    return NavigationHistory(
        current=back_stack[-1],
        back_stack=back_stack[:-1],
        forward_stack=(*forward_stack, current),
    )


def move_forward(
    *,
    current: Location,
    back_stack: tuple[Location, ...],
    forward_stack: tuple[Location, ...],
) -> NavigationHistory:
    if not forward_stack:
        raise RouteDeckValidationError("Forward navigation is not available")
    return NavigationHistory(
        current=forward_stack[-1],
        back_stack=(*back_stack, current),
        forward_stack=forward_stack[:-1],
    )


__all__ = [
    "NavigationHistory",
    "enter_location",
    "move_back",
    "move_forward",
]
