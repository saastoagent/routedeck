"""Explicitly test-only support package for RouteDeck consumers."""

from .scripted_model import (
    ScriptedModelCall,
    ScriptedTextModel,
    ScriptedToolModel,
    tool_call,
)

__all__ = [
    "ScriptedModelCall",
    "ScriptedTextModel",
    "ScriptedToolModel",
    "tool_call",
]
