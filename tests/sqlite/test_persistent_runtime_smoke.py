from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet

from medusa_agent.bindings import bind_medusa_app
from medusa_agent.composition import compile_medusa_app_spec
from medusa_agent.features.catalog import CatalogRouteKeyValidator
from medusa_agent.features.checkout import EncryptedCheckoutPrivateFormReader
from medusa_agent.medusa.client.models import CreateCartRequest, CreateCartResult
from medusa_agent.session import BuyerMarket, create_medusa_session
from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.events import (
    RouteDeckEvent,
    PublicEventPayload,
    RouteDeckEventType,
)
from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationStatus,
)
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationEvidence,
    OperationPhase,
    OperationSource,
)
from routedeck_core.contracts.session import (
    OperationAttempt,
    OperationAttemptStatus,
    OperationState,
    PendingReview,
    PrivateDraft,
    ReviewResolution,
    StoredOperationAttempt,
)
from routedeck_core.ports.session_store import SessionStoreError, SessionStoreErrorCode
from routedeck_core.runtime_defaults import UtcClock
from routedeck_core.state.aggregate import RouteDeckSessionAggregate
from routedeck_core.state.leases import TurnClaim, TurnOwnerKind
from routedeck_sqlalchemy import (
    FernetSensitiveCodec,
    RouteDeckInstanceAlreadyRunning,
    SqlAlchemyRuntimeResources,
    SqlAlchemySessionStore,
    open_sqlalchemy_routedeck_runtime,
)


class _UnusedMedusaClient:
    async def create_cart(self, request: CreateCartRequest) -> CreateCartResult:
        del request
        raise AssertionError("persistence smoke does not call Medusa")


class _Notifier:
    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        del session_id, events


class _Ids:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def __call__(self, kind: str) -> str:
        self._counts[kind] += 1
        return f"{kind}-{self._counts[kind]}"


@pytest.mark.asyncio
async def test_medusa_session_review_reopens_and_replays_after_restart(
    tmp_path,
) -> None:
    database_path = tmp_path / "routedeck.sqlite"
    key = Fernet.generate_key()
    clock = UtcClock()
    notifier = _Notifier()
    ids = _Ids()
    market = BuyerMarket(
        region_handle="region-in",
        country_code="in",
        currency_code="inr",
        sales_channel_handle="web",
    )
    compiled = compile_medusa_app_spec()
    client = _UnusedMedusaClient()

    async def keep_created_session(_services, snapshot):
        return snapshot

    async def open_runtime(instance_id: str):
        def application_factory(resources: SqlAlchemyRuntimeResources):
            return bind_medusa_app(
                app=compiled,
                client=client,
                private_forms=EncryptedCheckoutPrivateFormReader(
                    resources.store,
                    resources.codec,
                ),
                configured_payment_provider_id="payment-provider-test",
                buyer_country_code=market.country_code,
                handlers={},
                providers={},
                guards={},
            )

        return await open_sqlalchemy_routedeck_runtime(
            compiled_app=compiled,
            application_factory=application_factory,
            session_factory=lambda app, session_id: create_medusa_session(
                app=app,
                session_id=session_id,
                market=market,
            ),
            session_initializer=keep_created_session,
            public_key_validator_factory=CatalogRouteKeyValidator.from_session,
            agent_driver_factory=None,
            database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
            encryption_key=key,
            instance_id=instance_id,
            clock=clock,
            notifier=notifier,
            id_factory=ids,
            review_ttl=timedelta(minutes=10),
            resume_capability_ttl=timedelta(hours=24),
            default_session_id="buyer-session-1",
        )

    first_runtime = await open_runtime("first")
    first_store = first_runtime.services.store
    codec = first_runtime.private_form_codec
    with pytest.raises(RouteDeckInstanceAlreadyRunning):
        await SqlAlchemySessionStore.open(
            f"sqlite+pysqlite:///{database_path.as_posix()}",
            instance_id="fenced-second",
            codec=FernetSensitiveCodec(key),
        )

    created = await first_store.create(
        create_medusa_session(
            app=compiled,
            session_id="buyer-session-1",
            market=market,
        )
    )
    creation_first = await first_store.create_for_request(
        create_medusa_session(
            app=compiled,
            session_id="buyer-session-created-once",
            market=market,
        ),
        "session-create-request-1",
        "session-create-fingerprint-1",
    )
    creation_replay = await first_store.create_for_request(
        create_medusa_session(
            app=compiled,
            session_id="buyer-session-not-created",
            market=market,
        ),
        "session-create-request-1",
        "session-create-fingerprint-1",
    )
    assert creation_replay == creation_first
    with pytest.raises(SessionStoreError) as reused_creation:
        await first_store.create_for_request(
            create_medusa_session(
                app=compiled,
                session_id="buyer-session-not-created-2",
                market=market,
            ),
            "session-create-request-1",
            "different-session-create-fingerprint",
        )
    assert reused_creation.value.code is SessionStoreErrorCode.REQUEST_ID_REUSED
    chat_lease = await first_store.acquire_turn(
        TurnClaim(
            session_id=created.session_id,
            expected_session_version=created.session_version,
            request_id="chat-1",
            request_fingerprint="chat-fingerprint-1",
            owner_kind=TurnOwnerKind.CHAT,
        )
    )
    turns = (
        FinalizedConversationTurn(
            turn_id="buyer-turn-1",
            role=ConversationRole.USER,
            content="private buyer hello",
            request_id="chat-1",
        ),
        FinalizedConversationTurn(
            turn_id="assistant-turn-1",
            role=ConversationRole.ASSISTANT,
            content="private assistant reply",
            request_id="chat-1",
        ),
    )
    chat_state = (
        RouteDeckSessionAggregate(created.state)
        .append_conversation_turns(turns)
        .record_public_events(1)
        .commit()
    )
    chat_event = RouteDeckEvent(
        event_id="event-chat-1",
        cursor=chat_state.event_cursor,
        event_type=RouteDeckEventType.TURN_FINALIZED,
        session_id=created.session_id,
        session_version=chat_state.session_version,
        projection_version=chat_state.projection_version,
        created_at=clock.now(),
        payload=PublicEventPayload(
            node_id=chat_state.current.node_id,
            request_id="chat-1",
            status_code=chat_state.public_state.status_code,
        ),
    )
    chat_snapshot = await first_store.finalize_turn(
        chat_lease,
        created.session_version,
        chat_state,
        turns,
        (chat_event,),
        MutationCommit(
            kind=MutationKind.CHAT,
            status=MutationStatus.COMPLETED,
        ),
    )

    draft_lease = await first_store.acquire_turn(
        TurnClaim(
            session_id=created.session_id,
            expected_session_version=chat_snapshot.session_version,
            request_id="draft-1",
            request_fingerprint="draft-fingerprint-1",
            owner_kind=TurnOwnerKind.SURFACE,
        )
    )
    draft_state = (
        RouteDeckSessionAggregate(chat_snapshot.state)
        .store_private_draft(
            PrivateDraft(
                form_id="contact",
                field_names=("email",),
                revision=1,
                complete=True,
            )
        )
        .commit()
    )
    draft_snapshot = await first_store.save_private_blob(
        draft_lease,
        chat_snapshot.session_version,
        "contact",
        codec.encrypt(b'{"email":"buyer@example.test"}'),
        draft_state,
        (),
        MutationCommit(
            kind=MutationKind.PRIVATE_FORM,
            status=MutationStatus.COMPLETED,
            result={"complete": True, "form_id": "contact", "revision": 1},
        ),
    )
    chat_mutation = await first_store.find_mutation(
        created.session_id,
        "chat-1",
    )
    private_mutation = await first_store.find_mutation(
        created.session_id,
        "draft-1",
    )
    assert chat_mutation is not None
    assert chat_mutation.status is MutationStatus.COMPLETED
    assert private_mutation is not None
    assert private_mutation.kind is MutationKind.PRIVATE_FORM
    assert private_mutation.request_fingerprint == "draft-fingerprint-1"
    await first_store.release_turn(draft_lease)

    review_lease = await first_store.acquire_turn(
        TurnClaim(
            session_id=created.session_id,
            expected_session_version=draft_snapshot.session_version,
            request_id="review-proposal-1",
            request_fingerprint="review-request-fingerprint-1",
            owner_kind=TurnOwnerKind.SURFACE,
        )
    )
    attempt = OperationAttempt(
        attempt_id="attempt-review-1",
        request_id="review-proposal-1",
        request_fingerprint="review-request-fingerprint-1",
        operation_id="checkout.place_order",
        source=OperationSource.SURFACE,
        expected_session_version=draft_snapshot.session_version,
        context_fingerprint="context-fingerprint-1",
        status=OperationAttemptStatus.REVIEW_PENDING,
    )
    review = PendingReview(
        review_id="review-1",
        attempt=attempt,
        operation_spec_version="checkout.place_order.v1",
        proposal_fingerprint="proposal-fingerprint-1",
        projection_version=draft_snapshot.projection_version,
        authoritative_context_fingerprint="context-fingerprint-1",
        expires_at=clock.now() + timedelta(minutes=10),
        resolution=ReviewResolution.PENDING,
    )
    record = StoredOperationAttempt(
        attempt=attempt,
        review=review,
        disposition=OperationDisposition.REQUIRES_REVIEW,
        evidence=OperationEvidence(
            source=OperationSource.SURFACE,
            phases=(
                OperationPhase.RECEIVED,
                OperationPhase.LEASE_ACQUIRED,
                OperationPhase.VALIDATED,
                OperationPhase.CONTEXT_REFRESHED,
                OperationPhase.GUARDS_PASSED,
                OperationPhase.REVIEW_STAGED,
            ),
            attempt_id=attempt.attempt_id,
            request_fingerprint=attempt.request_fingerprint,
        ),
    )
    public_state = draft_snapshot.state.public_state.model_copy(
        update={
            "status_code": "review_pending",
            "status_message": "Review the order before placement.",
        }
    )
    review_state = (
        RouteDeckSessionAggregate(draft_snapshot.state)
        .set_operation_state(
            OperationState(
                active_attempt=attempt,
                pending_review=review,
            )
        )
        .set_public_state(public_state)
        .record_public_events(1)
        .commit()
    )
    review_event = RouteDeckEvent(
        event_id="event-review-1",
        cursor=review_state.event_cursor,
        event_type=RouteDeckEventType.OPERATION_CHANGED,
        session_id=created.session_id,
        session_version=review_state.session_version,
        projection_version=review_state.projection_version,
        created_at=clock.now(),
        payload=PublicEventPayload(
            node_id=review_state.current.node_id,
            operation_id=attempt.operation_id,
            request_id=attempt.request_id,
            status_code="review_pending",
        ),
    )
    review_snapshot = await first_store.stage_review(
        review_lease,
        draft_snapshot.session_version,
        record,
        review_state,
        (review_event,),
    )
    await first_store.release_turn(review_lease)

    await first_store.acquire_turn(
        TurnClaim(
            session_id=created.session_id,
            expected_session_version=review_snapshot.session_version,
            request_id="abandoned-chat-1",
            request_fingerprint="abandoned-chat-fingerprint-1",
            owner_kind=TurnOwnerKind.CHAT,
        )
    )
    await first_runtime.close()

    second_runtime = await open_runtime("second")
    second_store = second_runtime.services.store
    reopened = await second_store.load("buyer-session-1")
    persisted_review = await second_store.find_review(
        reopened.session_id, "review-1"
    )
    private_blob = await second_store.load_private_blob(
        reopened.session_id, "contact"
    )
    replay = await second_store.events_after(reopened.session_id, 0, 20)

    assert reopened.state.current.node_id == "buyer.home"
    assert reopened.state.operation is not None
    assert reopened.state.operation.pending_review is not None
    assert persisted_review is not None
    assert persisted_review.resolution is ReviewResolution.PENDING
    assert reopened.state.conversation[0].content == "private buyer hello"
    assert reopened.state.conversation[-1].status.value == "turn_interrupted"
    assert private_blob is not None
    assert codec.decrypt(private_blob) == b'{"email":"buyer@example.test"}'

    purge_lease = await second_store.acquire_turn(
        TurnClaim(
            session_id=reopened.session_id,
            expected_session_version=reopened.session_version,
            request_id="purge-private-form-1",
            request_fingerprint="purge-private-form-fingerprint-1",
            owner_kind=TurnOwnerKind.SURFACE,
        )
    )
    purged_state = (
        RouteDeckSessionAggregate(reopened.state)
        .set_private_state(
            reopened.state.private_state.model_copy(update={"drafts": ()})
        )
        .commit()
    )
    await second_store.commit_state(
        purge_lease,
        reopened.session_version,
        purged_state,
        (),
        MutationCommit(
            kind=MutationKind.PRIVATE_FORM,
            status=MutationStatus.COMPLETED,
        ),
    )
    await second_store.release_turn(purge_lease)
    assert (
        await second_store.load_private_blob(
            reopened.session_id,
            "contact",
        )
        is None
    )
    assert [event.event_type for event in replay.events] == [
        RouteDeckEventType.TURN_FINALIZED,
        RouteDeckEventType.OPERATION_CHANGED,
        RouteDeckEventType.TURN_INTERRUPTED,
    ]
    database_bytes = database_path.read_bytes()
    assert b"private buyer hello" not in database_bytes
    assert b"private assistant reply" not in database_bytes
    assert b"buyer@example.test" not in database_bytes
    await second_runtime.close()
