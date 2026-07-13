from __future__ import annotations

from .review_actions import ReviewActionMixin
from .review_results import ReviewResultMixin
from .review_staging import ReviewStagingMixin


class ReviewLifecycleMixin(
    ReviewActionMixin,
    ReviewStagingMixin,
    ReviewResultMixin,
):
    """Compose review actions, staging, and result translation."""


__all__ = ["ReviewLifecycleMixin"]
