"""Framework declaration and interaction validation errors."""


class RouteDeckValidationError(ValueError):
    """Raised when a RouteDeck declaration or interaction is invalid."""


class RouteDeckResumeCapabilityExpired(RouteDeckValidationError):
    """Raised when a session-bound location has only expired resume authority."""


__all__ = ["RouteDeckResumeCapabilityExpired", "RouteDeckValidationError"]
