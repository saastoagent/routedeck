from __future__ import annotations

from datetime import timedelta
from typing import Any


class OutcomeRuntimePorts:
    """Typed dependency surface shared by the outcome lifecycle slices."""

    app: Any
    store: Any
    executor: Any
    notifier: Any
    clock: Any
    id_factory: Any
    resume_capability_ttl: timedelta
    _failure: Any
    _failure_result: Any
    _supervised_phases: Any
    _current_node: Any
    _commit_supervision_failure: Any
    _evidence: Any
    _is_external_write: Any
    _mark_unknown: Any
    _valid_outcome_observation: Any
    _valid_outcome_effects: Any
    _unknown_write_outcome: Any
    _journaled_result: Any
    _commit_failure: Any
    _commit_success: Any
    _transition_for: Any
    _operation_event: Any
    _state_commit_failure_result: Any
    _result_from_stored: Any
    _completed_result: Any


__all__ = ["OutcomeRuntimePorts"]
