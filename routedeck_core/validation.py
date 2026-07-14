"""Framework declaration and interaction validation errors."""


class RouteDeckValidationError(ValueError):
    """Raised when a RouteDeck declaration or interaction is invalid."""


__all__ = ["RouteDeckValidationError"]
