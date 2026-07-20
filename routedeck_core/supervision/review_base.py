from __future__ import annotations

from datetime import timedelta
from typing import Any


class ReviewRuntimePorts:
    """Typed dependency surface shared by review lifecycle slices."""

    app: Any
    store: Any
    notifier: Any
    clock: Any
    id_factory: Any
    review_ttl: timedelta
    _result_from_stored: Any
    _failure_result: Any
    _failure: Any
    _resolve_entities: Any
    _refresh_context: Any
    _context_fingerprint: Any
    _evaluate_guards: Any
    _execute_attempt: Any
    _evidence: Any
    _operation_event: Any
    _supervised_phases: Any
    _commit_supervision_failure: Any
    _valid_json_object: Any
    _missing_review_result: Any
    _review_operation_request: Any
    _request_id_reused_result: Any
    _review_status_failure: Any
    _store_conflict_result: Any
    _resolve_invalid_review: Any


__all__ = ["ReviewRuntimePorts"]
