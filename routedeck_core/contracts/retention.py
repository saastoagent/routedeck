from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RouteDeckRetentionPolicy(BaseModel):
    """Typed retention limits for one RouteDeck session store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    unfinished_idle_ttl: timedelta
    unfinished_absolute_ttl: timedelta
    completed_ttl: timedelta
    event_retention_ttl: timedelta
    max_events_per_session: int = Field(ge=1)
    retain_operation_journal_until_session_delete: bool = True
    cleanup_on_startup: bool = True
    cleanup_interval: timedelta
    cleanup_batch_size: int = Field(ge=1, le=10_000)

    @model_validator(mode="after")
    def _positive_durations(self) -> RouteDeckRetentionPolicy:
        durations = {
            "unfinished_idle_ttl": self.unfinished_idle_ttl,
            "unfinished_absolute_ttl": self.unfinished_absolute_ttl,
            "completed_ttl": self.completed_ttl,
            "event_retention_ttl": self.event_retention_ttl,
            "cleanup_interval": self.cleanup_interval,
        }
        non_positive = tuple(
            name for name, value in durations.items() if value <= timedelta(0)
        )
        if non_positive:
            raise ValueError(
                "retention durations must be positive: " + ", ".join(non_positive)
            )
        if self.unfinished_idle_ttl > self.unfinished_absolute_ttl:
            raise ValueError("unfinished idle TTL cannot exceed absolute TTL")
        if not self.retain_operation_journal_until_session_delete:
            raise ValueError("operation journal retention must match session retention")
        return self

    @classmethod
    def standalone_default(cls) -> RouteDeckRetentionPolicy:
        return cls(
            unfinished_idle_ttl=timedelta(hours=24),
            unfinished_absolute_ttl=timedelta(days=7),
            completed_ttl=timedelta(hours=24),
            event_retention_ttl=timedelta(hours=24),
            max_events_per_session=1_000,
            retain_operation_journal_until_session_delete=True,
            cleanup_on_startup=True,
            cleanup_interval=timedelta(minutes=15),
            cleanup_batch_size=100,
        )


__all__ = ["RouteDeckRetentionPolicy"]
