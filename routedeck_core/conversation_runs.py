from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
from collections import OrderedDict
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import NoReturn

from .app import BoundApplication
from .contracts.conversation import (
    ConversationRole,
    ConversationRunFailure,
    ConversationRunKind,
    ConversationRunReview,
    ConversationRunSnapshot,
    ConversationRunStage,
    ConversationTurnStatus,
    EntryTurnDeclaration,
    FinalizedConversationTurn,
)
from .contracts.failures import FailureKind, RouteDeckFailure
from .contracts.mutations import MutationKind, MutationRecord, MutationStatus
from .contracts.session import SessionSnapshot
from .ports import (
    AgentReviewRequired,
    AgentTurnCompleted,
    AssistantInitiatedTrigger,
    AssistantTextDelta,
    AssistantTextReset,
    RouteDeckAgentDriver,
    RouteDeckAgentStreamError,
    RouteDeckAgentTurn,
    RouteDeckConversationTrigger,
    RouteDeckSessionStore,
    SessionStoreError,
    UserMessageTrigger,
)
from .ports.session_store import SessionStoreErrorCode
from .state.leases import TurnClaim, TurnLease, TurnOwnerKind
from .state.session import require_current_session
from .supervision import RouteDeckOperationRunner


_TERMINAL_CURSOR = 9_007_199_254_740_991
_MAX_RECENT_FAILURES = 128


@dataclass
class _Run:
    session_id: str
    request_id: str
    request_fingerprint: str
    kind: ConversationRunKind
    user_message: str | None = None
    user_turn_id: str | None = None
    stage: ConversationRunStage = ConversationRunStage.STARTING
    cursor: int = 0
    assistant_content: str = ""
    session_version: int | None = None
    projection_version: int | None = None
    turn_id: str | None = None
    failure: ConversationRunFailure | None = None
    review: ConversationRunReview | None = None
    latest_event: ConversationRunSnapshot | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    task: asyncio.Task[None] | None = None
    fatal_error: Exception | None = None

    def snapshot(self) -> ConversationRunSnapshot:
        return ConversationRunSnapshot(
            request_id=self.request_id,
            kind=self.kind,
            stage=self.stage,
            cursor=self.cursor,
            assistant_content=self.assistant_content,
            user_message=self.user_message,
            user_turn_id=self.user_turn_id,
            session_version=self.session_version,
            projection_version=self.projection_version,
            turn_id=self.turn_id,
            failure=self.failure,
            review=self.review,
        )

    async def publish(self, stage: ConversationRunStage, **updates: object) -> None:
        async with self.condition:
            if self.stage in {
                ConversationRunStage.COMPLETED,
                ConversationRunStage.INTERRUPTED,
            }:
                raise RuntimeError("a terminal conversation run cannot advance")
            self.stage = stage
            for name, value in updates.items():
                setattr(self, name, value)
            self.cursor += 1
            self.latest_event = self.snapshot()
            self.condition.notify_all()

    def initialize(self, stage: ConversationRunStage) -> None:
        self.stage = stage
        self.cursor += 1
        self.latest_event = self.snapshot()

    def restore_terminal(
        self, stage: ConversationRunStage, **updates: object
    ) -> None:
        self.stage = stage
        for name, value in updates.items():
            setattr(self, name, value)
        self.cursor = _TERMINAL_CURSOR
        self.latest_event = self.snapshot()

    async def fail(self, error: Exception) -> None:
        async with self.condition:
            self.fatal_error = error
            self.condition.notify_all()


class ConversationRunCoordinator:
    """Runtime-owned process-local task and transient conversation progress."""

    def __init__(
        self,
        *,
        app: BoundApplication,
        store: RouteDeckSessionStore,
        runner: RouteDeckOperationRunner,
        agent_driver: RouteDeckAgentDriver | None,
        id_factory,
    ) -> None:
        self.app = app
        self.store = store
        self.runner = runner
        self.agent_driver = agent_driver
        self.id_factory = id_factory
        self._runs: dict[tuple[str, str], _Run] = {}
        self._recent_failures: OrderedDict[
            tuple[str, str], Exception
        ] = OrderedDict()
        self._lock = asyncio.Lock()

    async def start_or_attach(
        self,
        *,
        session_id: str,
        request_id: str,
        expected_session_version: int,
        trigger: RouteDeckConversationTrigger,
    ) -> ConversationRunSnapshot:
        fingerprint = conversation_fingerprint(trigger)
        key = (session_id, request_id)
        async with self._lock:
            existing = self._runs.get(key)
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
                return existing.snapshot()
            recorded = await self.store.find_mutation(session_id, request_id)
            if recorded is not None:
                run = await self._from_mutation(session_id, recorded, trigger)
                return run.snapshot()
            if self.agent_driver is None:
                raise RuntimeError("RouteDeck conversation agent is not configured")
            snapshot = await self.store.load(session_id)
            require_current_session(self.app.app, snapshot.state)
            if snapshot.session_version != expected_session_version:
                raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
            run = _Run(
                session_id=session_id,
                request_id=request_id,
                request_fingerprint=fingerprint,
                kind=_trigger_kind(trigger),
                user_message=(trigger.message if isinstance(trigger, UserMessageTrigger) else None),
                user_turn_id=(
                    trigger.user_turn.turn_id
                    if isinstance(trigger, UserMessageTrigger)
                    else None
                ),
            )
            run.initialize(ConversationRunStage.STARTING)
            turn = await self.runner.begin_turn(
                TurnClaim(
                    session_id=session_id,
                    expected_session_version=snapshot.session_version,
                    request_id=request_id,
                    request_fingerprint=fingerprint,
                    owner_kind=TurnOwnerKind.CHAT,
                )
            )
            run.initialize(ConversationRunStage.AWAITING_MODEL)
            self._runs[key] = run
            run.task = asyncio.create_task(
                self._execute(run=run, turn=turn, trigger=trigger),
                name=f"routedeck-conversation-{request_id}",
            )
            return run.snapshot()

    async def get(self, session_id: str, request_id: str) -> ConversationRunSnapshot:
        run = await self._resolve_run(session_id, request_id)
        if run.fatal_error is not None:
            raise run.fatal_error
        return run.snapshot()

    async def events(
        self,
        session_id: str,
        request_id: str,
        after: int,
        heartbeat_seconds: float,
    ) -> AsyncIterator[ConversationRunSnapshot | None]:
        run = await self._resolve_run(session_id, request_id)
        if run.fatal_error is not None:
            raise run.fatal_error
        current = run.snapshot()
        if after > current.cursor:
            raise ConversationRunCursorInvalid(after)
        cursor = after
        while True:
            async with run.condition:
                if run.fatal_error is not None:
                    raise run.fatal_error
                latest = run.latest_event
                pending = (
                    (latest,)
                    if latest is not None and latest.cursor > cursor
                    else ()
                )
                if not pending and not run.snapshot().terminal:
                    try:
                        await asyncio.wait_for(run.condition.wait(), heartbeat_seconds)
                    except TimeoutError:
                        pending = ()
                    else:
                        if run.fatal_error is not None:
                            raise run.fatal_error
                        latest = run.latest_event
                        pending = (
                            (latest,)
                            if latest is not None and latest.cursor > cursor
                            else ()
                        )
            if not pending:
                async with run.condition:
                    if run.snapshot().terminal and cursor >= run.cursor:
                        return
                yield None
                continue
            for event in pending:
                yield event
                cursor = event.cursor
            async with run.condition:
                if run.snapshot().terminal and cursor >= run.cursor:
                    return

    async def ensure_declared_entry_run(
        self, snapshot: SessionSnapshot
    ) -> ConversationRunSnapshot | None:
        require_current_session(self.app.app, snapshot.state)
        node = self.app.app.require_node(snapshot.state.current.node_id)
        declaration = node.entry_turn
        if declaration is None:
            return None
        return await self.start_or_attach(
            session_id=snapshot.session_id,
            request_id=entry_turn_request_id(node.id, declaration),
            expected_session_version=snapshot.session_version,
            trigger=AssistantInitiatedTrigger(),
        )

    async def close(self) -> None:
        tasks = tuple(
            run.task for run in self._runs.values() if run.task is not None and not run.task.done()
        )
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _resolve_run(self, session_id: str, request_id: str) -> _Run:
        key = (session_id, request_id)
        async with self._lock:
            run = self._runs.get(key)
            if run is not None:
                return run
            recorded = await self.store.find_mutation(session_id, request_id)
            if recorded is not None:
                self._recent_failures.pop(key, None)
                return await self._from_mutation(session_id, recorded, None)
            failure = self._recent_failures.get(key)
            if failure is not None:
                self._recent_failures.move_to_end(key)
                raise failure
            raise ConversationRunNotFound(request_id)

    async def _evict_terminal(self, run: _Run) -> None:
        key = (run.session_id, run.request_id)
        async with self._lock:
            if self._runs.get(key) is run:
                self._runs.pop(key)
            self._recent_failures.pop(key, None)

    async def _remember_failure(self, run: _Run, error: Exception) -> None:
        key = (run.session_id, run.request_id)
        async with self._lock:
            if self._runs.get(key) is run:
                self._runs.pop(key)
            self._recent_failures[key] = error
            self._recent_failures.move_to_end(key)
            while len(self._recent_failures) > _MAX_RECENT_FAILURES:
                self._recent_failures.popitem(last=False)

    async def _execute(
        self,
        *,
        run: _Run,
        turn: TurnLease,
        trigger: RouteDeckConversationTrigger,
    ) -> None:
        event_stream: AsyncIterator | None = None
        try:
            agent_driver = self.agent_driver
            if agent_driver is None:
                raise RuntimeError("RouteDeck conversation agent is not configured")
            event_stream = agent_driver.stream(
                RouteDeckAgentTurn(
                    session_id=run.session_id,
                    request_id=run.request_id,
                    lease=turn,
                    trigger=trigger,
                )
            )
            async for event in event_stream:
                if isinstance(event, AssistantTextDelta):
                    if not event.content:
                        _invalid_agent_event("The agent emitted an empty text delta.")
                    await run.publish(
                        ConversationRunStage.GENERATING,
                        assistant_content=run.assistant_content + event.content,
                    )
                elif isinstance(event, AssistantTextReset):
                    await run.publish(
                        ConversationRunStage.GENERATING,
                        assistant_content="",
                    )
                elif isinstance(event, AgentReviewRequired):
                    if isinstance(trigger, AssistantInitiatedTrigger):
                        _invalid_agent_event(
                            "An assistant-initiated turn cannot require review."
                        )
                    await _close_stream(event_stream)
                    record = await self.store.find_mutation(
                        run.session_id, run.request_id
                    )
                    if (
                        record is None
                        or record.status is not MutationStatus.REQUIRES_REVIEW
                        or record.request_fingerprint != run.request_fingerprint
                    ):
                        raise SessionStoreError(
                            SessionStoreErrorCode.PERSISTENCE_FAILURE
                        )
                    result = record.result.to_dict()
                    await run.publish(
                        ConversationRunStage.COMPLETED,
                        session_version=record.committed_session_version,
                        projection_version=record.committed_projection_version,
                        review=ConversationRunReview(
                            operation_id=str(result["operation_id"]),
                            review_id=str(result["review_id"]),
                            expires_at=str(result["expires_at"]),
                        ),
                    )
                    await self._evict_terminal(run)
                    return
                elif isinstance(event, AgentTurnCompleted):
                    _validate_completed(trigger, event)
                    await _close_stream(event_stream)
                    current = await self.store.load(run.session_id)
                    completed = await self.runner.complete_turn(
                        turn,
                        expected_session_version=current.session_version,
                        turns=event.turns,
                    )
                    await run.publish(
                        ConversationRunStage.COMPLETED,
                        session_version=completed.session_version,
                        projection_version=completed.projection_version,
                        turn_id=event.assistant_turn_id,
                    )
                    await self._evict_terminal(run)
                    return
                else:
                    _invalid_agent_event(
                        "The agent emitted an unsupported conversation event."
                    )
            raise RouteDeckAgentStreamError(
                "agent_result_missing",
                "The agent did not return a terminal response.",
            )
        except asyncio.CancelledError:
            await self._interrupt(run, turn, event_stream)
        except Exception as error:
            await self._interrupt(run, turn, event_stream, error)

    async def _interrupt(
        self,
        run: _Run,
        turn: TurnLease,
        event_stream: AsyncIterator | None,
        error: Exception | None = None,
    ) -> None:
        if event_stream is not None:
            try:
                await _close_stream(event_stream)
            except Exception:
                pass
        failure = RouteDeckFailure(
            kind=FailureKind.INTERNAL,
            code=(
                error.code
                if isinstance(error, RouteDeckAgentStreamError)
                else "turn_interrupted"
            ),
            phase="agent_stream",
            correlation_id=secrets.token_urlsafe(12),
            request_id=run.request_id,
            public_message=(
                error.public_message
                if isinstance(error, RouteDeckAgentStreamError)
                else "The agent turn was interrupted."
            ),
        )
        try:
            current = await self.store.load(run.session_id)
            snapshot = await self.runner.interrupt_turn(
                turn,
                expected_session_version=current.session_version,
                failure=failure,
            )
        except Exception:
            persistence_error = SessionStoreError(
                SessionStoreErrorCode.PERSISTENCE_FAILURE
            )
            await run.fail(persistence_error)
            await self._remember_failure(run, persistence_error)
            return
        await run.publish(
            ConversationRunStage.INTERRUPTED,
            session_version=snapshot.session_version,
            projection_version=snapshot.projection_version,
            failure=ConversationRunFailure(
                code=failure.code,
                message=failure.public_message,
            ),
        )
        await self._evict_terminal(run)

    async def _from_mutation(
        self,
        session_id: str,
        record: MutationRecord,
        requested_trigger: RouteDeckConversationTrigger | None,
    ) -> _Run:
        if record.kind is not MutationKind.CHAT:
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        snapshot = await self.store.load(session_id)
        require_current_session(self.app.app, snapshot.state)
        request_turns = tuple(
            turn for turn in snapshot.state.conversation if turn.request_id == record.request_id
        )
        user = next((turn for turn in request_turns if turn.role is ConversationRole.USER), None)
        kind = _fingerprint_kind(record.request_fingerprint)
        if (
            requested_trigger is not None
            and conversation_fingerprint(requested_trigger)
            != record.request_fingerprint
        ):
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        if requested_trigger is not None and _trigger_kind(requested_trigger) is not kind:
            raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        if user is not None:
            inferred_trigger = UserMessageTrigger(
                message=user.content,
                user_turn=FinalizedConversationTurn(
                    turn_id=user.turn_id,
                    role=user.role,
                    content=user.content,
                    request_id=user.request_id,
                ),
            )
            if conversation_fingerprint(inferred_trigger) != record.request_fingerprint:
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        elif kind is ConversationRunKind.ASSISTANT_INITIATED:
            if (
                conversation_fingerprint(AssistantInitiatedTrigger())
                != record.request_fingerprint
            ):
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
        run = _Run(
            session_id=session_id,
            request_id=record.request_id,
            request_fingerprint=record.request_fingerprint,
            kind=kind,
            user_message=(user.content if user is not None else None),
            user_turn_id=(user.turn_id if user is not None else None),
        )
        if record.status is MutationStatus.COMPLETED:
            assistant = next(
                (
                    turn
                    for turn in reversed(request_turns)
                    if turn.role is ConversationRole.ASSISTANT
                    and turn.status is ConversationTurnStatus.FINALIZED
                ),
                None,
            )
            if assistant is None:
                raise RuntimeError("completed conversation mutation has no assistant turn")
            run.restore_terminal(
                ConversationRunStage.COMPLETED,
                assistant_content=assistant.content,
                session_version=record.committed_session_version,
                projection_version=record.committed_projection_version,
                turn_id=assistant.turn_id,
            )
            return run
        result = record.result.to_dict()
        if record.status is MutationStatus.REQUIRES_REVIEW:
            run.restore_terminal(
                ConversationRunStage.COMPLETED,
                session_version=record.committed_session_version,
                projection_version=record.committed_projection_version,
                review=ConversationRunReview(
                    operation_id=str(result["operation_id"]),
                    review_id=str(result["review_id"]),
                    expires_at=str(result["expires_at"]),
                ),
            )
            return run
        if record.status is MutationStatus.TURN_INTERRUPTED:
            run.restore_terminal(
                ConversationRunStage.INTERRUPTED,
                session_version=record.committed_session_version,
                projection_version=record.committed_projection_version,
                failure=ConversationRunFailure(
                    code=str(result["code"]), message=str(result["message"])
                ),
            )
            return run
        raise RuntimeError("conversation mutation status is invalid")


class ConversationRunNotFound(LookupError):
    pass


class ConversationRunCursorInvalid(ValueError):
    pass


def conversation_fingerprint(trigger: RouteDeckConversationTrigger) -> str:
    kind = _trigger_kind(trigger).value
    payload = (
        {"kind": "user_message", "message": trigger.message}
        if isinstance(trigger, UserMessageTrigger)
        else {"kind": "assistant_initiated"}
    )
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return f"rdconv1:{kind}:{hashlib.sha256(canonical).hexdigest()}"


def _fingerprint_kind(fingerprint: str) -> ConversationRunKind:
    prefix, separator, _digest = fingerprint.rpartition(":")
    if not separator:
        raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)
    if prefix == "rdconv1:user_message":
        return ConversationRunKind.USER_MESSAGE
    if prefix == "rdconv1:assistant_initiated":
        return ConversationRunKind.ASSISTANT_INITIATED
    raise SessionStoreError(SessionStoreErrorCode.PERSISTENCE_FAILURE)


def entry_turn_request_id(node_id: str, declaration: EntryTurnDeclaration) -> str:
    canonical = json.dumps(
        {
            "declaration_id": declaration.id,
            "node_id": node_id,
            "occurrence": declaration.occurrence.value,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"entry-turn:{hashlib.sha256(canonical).hexdigest()}"


def _trigger_kind(trigger: RouteDeckConversationTrigger) -> ConversationRunKind:
    return (
        ConversationRunKind.USER_MESSAGE
        if isinstance(trigger, UserMessageTrigger)
        else ConversationRunKind.ASSISTANT_INITIATED
    )


def _validate_completed(
    trigger: RouteDeckConversationTrigger, event: AgentTurnCompleted
) -> None:
    turns: Sequence[FinalizedConversationTurn] = event.turns
    if (
        not turns
        or turns[-1].role is not ConversationRole.ASSISTANT
        or turns[-1].turn_id != event.assistant_turn_id
        or not turns[-1].content
    ):
        _invalid_agent_event("The agent returned invalid finalized turns.")
    if isinstance(trigger, AssistantInitiatedTrigger) and len(turns) != 1:
        _invalid_agent_event("An assistant-initiated turn must finalize one turn.")
    if isinstance(trigger, UserMessageTrigger) and turns[0] != trigger.user_turn:
        _invalid_agent_event("A user turn must retain its user marker.")


async def _close_stream(stream: object) -> None:
    close = getattr(stream, "aclose", None)
    if callable(close):
        await close()


def _invalid_agent_event(message: str) -> NoReturn:
    raise RouteDeckAgentStreamError("agent_stream_contract_invalid", message)


__all__ = [
    "ConversationRunCoordinator",
    "ConversationRunCursorInvalid",
    "ConversationRunNotFound",
    "conversation_fingerprint",
    "entry_turn_request_id",
]
