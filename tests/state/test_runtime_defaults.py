from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from routedeck_core.runtime_defaults import InProcessEventNotifier


class _TaskRecordingCondition(asyncio.Condition):
    wait_task: asyncio.Task[object] | None = None

    async def wait_for(self, predicate):  # type: ignore[no-untyped-def]
        self.wait_task = asyncio.current_task()
        return await super().wait_for(predicate)


@pytest.mark.asyncio
async def test_notifier_keeps_condition_wait_in_the_lock_owning_task() -> None:
    condition = _TaskRecordingCondition()
    notifier = InProcessEventNotifier(_condition=condition)
    waiting = asyncio.create_task(
        notifier.wait_for_events(
            "session-task-ownership",
            after_cursor=0,
            timeout=timedelta(seconds=30),
        )
    )
    while condition.wait_task is None:
        await asyncio.sleep(0)

    assert condition.wait_task is waiting

    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting


@pytest.mark.asyncio
async def test_notifier_wait_can_be_cancelled_without_corrupting_its_lock() -> None:
    notifier = InProcessEventNotifier()
    waiting = asyncio.create_task(
        notifier.wait_for_events(
            "session-cancelled-wait",
            after_cursor=0,
            timeout=timedelta(seconds=30),
        )
    )
    await asyncio.sleep(0)

    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    assert not await notifier.wait_for_events(
        "session-after-cancellation",
        after_cursor=0,
        timeout=timedelta(milliseconds=1),
    )
