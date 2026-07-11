from __future__ import annotations

import routedeck_core
import routedeck_fastapi
import routedeck_langgraph
import routedeck_sqlite


_FRAMEWORK_PACKAGES = (
    routedeck_core,
    routedeck_fastapi,
    routedeck_langgraph,
    routedeck_sqlite,
)


def framework_packages() -> tuple[str, ...]:
    """Return the public RouteDeck packages wired by this composition root."""

    return tuple(package.__name__ for package in _FRAMEWORK_PACKAGES)


__all__ = ["framework_packages"]
