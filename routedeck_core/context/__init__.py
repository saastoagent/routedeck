"""Scoped, default-deny RouteDeck context APIs."""

from .providers import OperationContextScope
from .scope import ContextScopeBuilder

__all__ = ["ContextScopeBuilder", "OperationContextScope"]
