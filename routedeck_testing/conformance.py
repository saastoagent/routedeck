from __future__ import annotations

import inspect
from typing import TypeVar, get_type_hints

from routedeck_core.ports.session_store import RouteDeckSessionStore


StoreT = TypeVar("StoreT")


_SESSION_STORE_METHODS = (
    "create",
    "create_for_request",
    "load",
    "find_attempt",
    "find_review",
    "find_mutation",
    "acquire_turn",
    "claim_child_attempt",
    "release_child_attempt",
    "stage_review",
    "claim_execution",
    "recover_execution_claim",
    "record_execution_started",
    "record_execution_result",
    "commit_state",
    "finalize_turn",
    "interrupt_turn",
    "commit_attempt",
    "commit_supervision",
    "mark_external_outcome_unknown",
    "release_turn",
    "events_after",
    "load_private_blob",
    "save_private_blob",
)


def assert_session_store_conforms(store: StoreT) -> StoreT:
    missing = tuple(
        method_name
        for method_name in _SESSION_STORE_METHODS
        if not callable(getattr(store, method_name, None))
    )
    non_async = tuple(
        method_name
        for method_name in _SESSION_STORE_METHODS
        if method_name not in missing
        and not inspect.iscoroutinefunction(getattr(store, method_name))
    )
    incompatible: list[str] = []
    for method_name in _SESSION_STORE_METHODS:
        if method_name in missing or method_name in non_async:
            continue
        expected = RouteDeckSessionStore.__dict__[method_name]
        actual = getattr(type(store), method_name)
        expected_signature = inspect.signature(expected)
        actual_signature = inspect.signature(actual)
        expected_parameters = tuple(
            (name, parameter.kind, parameter.default)
            for name, parameter in expected_signature.parameters.items()
        )
        actual_parameters = tuple(
            (name, parameter.kind, parameter.default)
            for name, parameter in actual_signature.parameters.items()
        )
        if expected_parameters != actual_parameters:
            incompatible.append(method_name)
            continue
        if get_type_hints(expected) != get_type_hints(actual):
            incompatible.append(method_name)

    if missing or non_async or incompatible:
        problems: list[str] = []
        if missing:
            problems.append(f"missing methods: {', '.join(missing)}")
        if non_async:
            problems.append(f"non-async methods: {', '.join(non_async)}")
        if incompatible:
            problems.append(f"incompatible signatures: {', '.join(incompatible)}")
        raise TypeError(
            "RouteDeckSessionStore conformance failed: " + "; ".join(problems)
        )
    return store


__all__ = ["assert_session_store_conforms"]
