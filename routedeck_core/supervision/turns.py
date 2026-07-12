from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..contracts.conversation import (
    ConversationRole,
    ConversationTurn,
    ConversationTurnStatus,
    FinalizedConversationTurn,
)
from ..contracts.events import (
    CanonicalRouteDeckEvent,
    PublicEventPayload,
    RouteDeckEventKind,
)
from ..contracts.failures import RouteDeckFailure
from ..contracts.mutations import MutationCommit, MutationKind, MutationStatus
from ..contracts.projection import FrozenJsonObject
from ..contracts.session import RouteDeckSession, SessionSnapshot
from ..ports.notifier import notify_event_wakeup
from ..ports.session_store import SessionStoreError, SessionStoreErrorCode
from ..state.leases import TurnClaim, TurnLease, TurnOwnerKind
from ..state.reducer import (
    ConversationTurnsStored,
    PublicEventsRecorded,
    PublicSessionStateStored,
    reduce_session_batch,
)
from ..state.session import require_compatible_session


class TurnLifecycleMixin:
    app: Any
    store: Any
    notifier: Any
    clock: Any
    id_factory: Any

    async def begin_turn(self, claim: TurnClaim) -> TurnLease:
        if claim.owner_kind is not TurnOwnerKind.CHAT:
            raise ValueError("begin_turn requires a chat turn claim")
        session = (await self.store.load(claim.session_id)).state
        require_compatible_session(self.app.app, session)
        if session.session_version != claim.expected_session_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        return await self.store.acquire_turn(claim)

    async def complete_turn(
        self,
        turn: TurnLease,
        expected_session_version: int,
        turns: Sequence[FinalizedConversationTurn],
    ) -> SessionSnapshot:
        finalized = tuple(turns)
        if not finalized or any(
            not isinstance(item, FinalizedConversationTurn) for item in finalized
        ):
            raise ValueError("complete_turn requires finalized conversation turns")
        if any(item.request_id != turn.request_id for item in finalized):
            raise ValueError("finalized content belongs to another turn")
        session = (await self.store.load(turn.session_id)).state
        next_state = reduce_session_batch(
            session,
            (
                ConversationTurnsStored(turns=finalized),
                PublicEventsRecorded(count=1),
            ),
        )
        event = self._turn_event(
            state=next_state,
            event_type=RouteDeckEventKind.TURN_FINALIZED,
            request_id=turn.request_id,
            status_code=next_state.public_state.status_code,
        )
        snapshot = await self.store.finalize_turn(
            turn,
            expected_session_version,
            next_state,
            finalized,
            (event,),
            MutationCommit(
                kind=MutationKind.CHAT,
                status=MutationStatus.COMPLETED,
            ),
        )
        await notify_event_wakeup(self.notifier, turn.session_id, (event,))
        return snapshot

    async def interrupt_turn(
        self,
        turn: TurnLease,
        expected_session_version: int,
        failure: RouteDeckFailure,
    ) -> SessionSnapshot:
        if failure.request_id not in {None, turn.request_id}:
            raise ValueError("turn interruption failure belongs to another request")
        session = (await self.store.load(turn.session_id)).state
        interrupted = ConversationTurn(
            turn_id=self.id_factory("turn"),
            role=ConversationRole.ASSISTANT,
            content="",
            request_id=turn.request_id,
            status=ConversationTurnStatus.INTERRUPTED,
        )
        public_state = session.public_state.model_copy(
            update={
                "status_code": "turn_interrupted",
                "status_message": failure.public_message,
                "failure": failure,
            }
        )
        next_state = reduce_session_batch(
            session,
            (
                ConversationTurnsStored(turns=(interrupted,)),
                PublicSessionStateStored(state=public_state),
                PublicEventsRecorded(count=1),
            ),
        )
        event = self._turn_event(
            state=next_state,
            event_type=RouteDeckEventKind.TURN_INTERRUPTED,
            request_id=turn.request_id,
            status_code=public_state.status_code,
            failure=failure,
        )
        snapshot = await self.store.interrupt_turn(
            turn,
            expected_session_version,
            next_state,
            failure,
            (event,),
            MutationCommit(
                kind=MutationKind.CHAT,
                status=MutationStatus.TURN_INTERRUPTED,
                result=FrozenJsonObject(
                    {
                        "code": failure.code,
                        "message": failure.public_message,
                    }
                ),
            ),
        )
        await notify_event_wakeup(self.notifier, turn.session_id, (event,))
        return snapshot

    def _turn_event(
        self,
        *,
        state: RouteDeckSession,
        event_type: RouteDeckEventKind,
        request_id: str,
        status_code: str,
        failure: RouteDeckFailure | None = None,
    ) -> CanonicalRouteDeckEvent:
        return CanonicalRouteDeckEvent(
            event_id=self.id_factory("event"),
            cursor=state.event_cursor,
            event_type=event_type,
            session_id=state.session_id,
            session_version=state.session_version,
            projection_version=state.projection_version,
            created_at=self.clock.now(),
            payload=PublicEventPayload(
                node_id=state.current.node_id,
                request_id=request_id,
                status_code=status_code,
                failure=failure,
            ),
        )


__all__ = ["TurnLifecycleMixin"]
