from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from routedeck_core.contracts.retention import RouteDeckRetentionPolicy
from routedeck_core.ports.codec import SensitiveCodec

from ..recovery import recover_abandoned_turn_batch
from ..sessions import SessionRepository
from ..turns import TurnRepository
from .lifecycle import _StoreLifecycle


class _MaintenanceTransactions:
    def __init__(
        self,
        *,
        lifecycle: _StoreLifecycle,
        codec: SensitiveCodec,
        retention_policy: RouteDeckRetentionPolicy,
        sessions: SessionRepository,
        turns: TurnRepository,
    ) -> None:
        self._lifecycle = lifecycle
        self._codec = codec
        self._retention_policy = retention_policy
        self._sessions = sessions
        self._turns = turns

    async def cleanup_expired(self) -> int:
        return await self._lifecycle.write(
            lambda database, now: self._sessions.cleanup_expired(database, now=now)
        )

    async def recover_abandoned_turns(self) -> None:
        while True:
            recovered = await self._lifecycle.write(
                self.recover_abandoned_turn_batch
            )
            if recovered < self._retention_policy.cleanup_batch_size:
                return

    def recover_abandoned_turn_batch(
        self,
        database: Session,
        now: datetime,
    ) -> int:
        return recover_abandoned_turn_batch(
            database,
            now,
            sessions=self._sessions,
            turns=self._turns,
            codec=self._codec,
            retention_policy=self._retention_policy,
            application_lease=self._lifecycle.runtime.application_lease,
        )
