from __future__ import annotations

from .fingerprints import (
    canonical_json_fingerprint,
    canonical_operation_spec_version,
    canonical_request_fingerprint,
)
from .outcome_commits import OutcomeCommitMixin
from .outcome_execution import OutcomeExecutionMixin
from .outcome_results import OutcomeResultMixin


class OutcomeLifecycleMixin(
    OutcomeExecutionMixin,
    OutcomeCommitMixin,
    OutcomeResultMixin,
):
    """Compose execution, commit, and result-validation outcome slices."""


__all__ = [
    "OutcomeLifecycleMixin",
    "canonical_json_fingerprint",
    "canonical_operation_spec_version",
    "canonical_request_fingerprint",
]
