from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from routedeck_core.contracts.events import EventPage, PublicRouteDeckEvent, RouteDeckEvent

from .dependencies import EventWakeupNotifier, SseSettings


class EventReplayStore(Protocol):
    async def events_after(
        self,
        session_id: str,
        cursor: int,
        limit: int,
    ) -> EventPage: ...


class StreamResetPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: Literal["stream_reset_required"] = "stream_reset_required"
    requested_after: int = Field(ge=0)
    retained_from_cursor: int | None = Field(default=None, ge=0)


def encode_event(event: RouteDeckEvent) -> bytes:
    """Encode one durable, public RouteDeck event as an SSE frame."""

    public_event = PublicRouteDeckEvent.from_durable_event(event).model_dump(mode="json")
    data = json.dumps(
        public_event,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        f"id: {event.cursor}\nevent: {event.event_type.value}\ndata: {data}\n\n"
    ).encode("utf-8")


def encode_stream_reset(
    *,
    requested_after: int,
    retained_from_cursor: int | None,
) -> bytes:
    data = json.dumps(
        StreamResetPayload(
            requested_after=requested_after,
            retained_from_cursor=retained_from_cursor,
        ).model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"event: stream_reset_required\ndata: {data}\n\n".encode("utf-8")


def encode_heartbeat() -> bytes:
    """Heartbeats are comments and deliberately have no event cursor."""

    return b": heartbeat\n\n"


async def stream_events(
    *,
    session_id: str,
    after_cursor: int,
    store: EventReplayStore,
    notifier: EventWakeupNotifier,
    settings: SseSettings,
    initial_page: EventPage | None = None,
) -> AsyncIterator[bytes]:
    """Replay durable events before following cursor-aware wakeups."""

    # Flush the streaming response immediately even when the client is already
    # at the latest cursor. Without an initial frame, browsers behind a proxy
    # can remain in "connecting" until the first event or timed heartbeat.
    yield encode_heartbeat()
    cursor = after_cursor
    page = initial_page
    while True:
        if page is None:
            page = await store.events_after(
                session_id,
                cursor,
                settings.replay_batch_size,
            )
        if page.reset_required:
            yield encode_stream_reset(
                requested_after=cursor,
                retained_from_cursor=page.retained_from_cursor,
            )
            return

        for event in page.events:
            if event.cursor <= cursor:
                continue
            if event.cursor != cursor + 1:
                yield encode_stream_reset(
                    requested_after=cursor,
                    retained_from_cursor=event.cursor,
                )
                return
            yield encode_event(event)
            cursor = event.cursor

        if page.events and page.next_cursor != cursor:
            raise RuntimeError("event page cursor does not match its final event")
        if page.has_more:
            if not page.events:
                raise RuntimeError("event page cannot have more without progress")
            page = None
            continue
        if not settings.follow:
            return

        woke = await notifier.wait_for_events(
            session_id,
            cursor,
            settings.heartbeat_interval,
        )
        if not woke:
            yield encode_heartbeat()
        page = None


__all__ = [
    "encode_event",
    "encode_heartbeat",
    "encode_stream_reset",
    "StreamResetPayload",
    "stream_events",
]
