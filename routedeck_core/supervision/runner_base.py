from __future__ import annotations

from typing import Any


class RunnerRuntimePorts:
    """Typed dependency surface shared by operation-runner support slices."""

    app: Any
    store: Any
    executor: Any
    clock: Any
    notifier: Any
    id_factory: Any
    review_ttl: Any
    resume_capability_ttl: Any
    _is_external_write: Any
    _operation_event: Any
    _evidence: Any
    _result_from_stored: Any
    _store_conflict_result: Any
    _route_entry_session: Any
    _commit_failure: Any
    _commit_success: Any
    _recover_non_write_started: Any
    _mark_unknown: Any
    _failure: Any
    _supervised_phases: Any
    _failure_result: Any


__all__ = ["RunnerRuntimePorts"]
