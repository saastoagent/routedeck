from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from routedeck_core.app import ApplicationSpec, FeatureSpec, compile_app
from routedeck_core.contracts.application import NodeSpec
from routedeck_core.contracts.events import (
    RouteDeckEvent,
    EventPage,
    PublicEventPayload,
    RouteDeckEventType,
)
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationEvidence,
    OperationPhase,
    OperationRequest,
    OperationResult,
    OperationReview,
    OperationSource,
)
from routedeck_core.contracts.mutations import MutationCommit, MutationRecord
from routedeck_core.contracts.navigation import DeepLinkPolicy, NodeKind, RouteSpec
from routedeck_core.contracts.projection import (
    ClassifiedValue,
    DataClassification,
    FrozenJson,
    FrozenJsonObject,
)
from routedeck_core.contracts.session import (
    PrivateSessionState,
    PublicSessionState,
    PublicSurfaceState,
    RouteDeckSession,
    SessionSnapshot,
)
from routedeck_core.contracts.surfaces import SurfaceSlotsSpec, SurfaceSpec
from routedeck_core.ports import SessionStoreError, SessionStoreErrorCode
from routedeck_core.projection import ProjectionProjector
from routedeck_core.state import create_session
from routedeck_core.state.leases import TurnClaim, TurnLease
from routedeck_fastapi import RouteDeckDependencies, SseSettings


BACKEND_ROOT = (
    Path(__file__).resolve().parents[2] / "examples" / "medusa-agent" / "backend"
)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import create_medusa_app  # noqa: E402
from medusa_agent.composition import compile_medusa_app_spec  # noqa: E402
from medusa_agent.session import BuyerMarket, create_medusa_session  # noqa: E402


class SmokeCodec:
    def encrypt(self, value: bytes) -> bytes:
        return b"smoke-encrypted:" + value[::-1]

    def decrypt(self, value: bytes) -> bytes:
        prefix = b"smoke-encrypted:"
        if not value.startswith(prefix):
            raise ValueError("invalid smoke ciphertext")
        return value[len(prefix) :][::-1]


class SmokeNotifier:
    async def notify(
        self,
        session_id: str,
        events: Sequence[RouteDeckEvent],
    ) -> None:
        del session_id, events


class SmokeStore:
    def __init__(self) -> None:
        self.session: RouteDeckSession | None = None
        self.events: list[RouteDeckEvent] = []
        self.private_blobs: dict[str, bytes] = {}
        self.lease: TurnLease | None = None
        self.claim: TurnClaim | None = None
        self.creation_requests: dict[str, tuple[str, str]] = {}
        self.mutations: dict[str, MutationRecord] = {}

    async def create(self, initial: RouteDeckSession) -> SessionSnapshot:
        self.session = initial
        return SessionSnapshot(state=initial)

    async def create_for_request(
        self,
        initial: RouteDeckSession,
        request_id: str,
        request_fingerprint: str,
    ) -> SessionSnapshot:
        existing = self.creation_requests.get(request_id)
        if existing is not None:
            fingerprint, session_id = existing
            if fingerprint != request_fingerprint:
                raise SessionStoreError(SessionStoreErrorCode.REQUEST_ID_REUSED)
            return await self.load(session_id)
        snapshot = await self.create(initial)
        self.creation_requests[request_id] = (
            request_fingerprint,
            initial.session_id,
        )
        return snapshot

    async def load(self, session_id: str) -> SessionSnapshot:
        if self.session is None or self.session.session_id != session_id:
            raise SessionStoreError(SessionStoreErrorCode.SESSION_NOT_FOUND)
        return SessionSnapshot(state=self.session)

    async def acquire_turn(self, claim: TurnClaim) -> TurnLease:
        snapshot = await self.load(claim.session_id)
        if snapshot.session_version != claim.expected_session_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        self.lease = TurnLease(
            capability=SecretStr(f"lease:{claim.request_id}"),
            fencing_token=1,
            session_id=claim.session_id,
            request_id=claim.request_id,
        )
        self.claim = claim
        return self.lease

    async def find_attempt(self, session_id: str, request_id: str):
        del session_id, request_id
        return None

    async def find_mutation(
        self,
        session_id: str,
        request_id: str,
    ) -> MutationRecord | None:
        await self.load(session_id)
        return self.mutations.get(request_id)

    async def release_turn(self, lease: TurnLease) -> None:
        if lease != self.lease:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        self.lease = None
        self.claim = None

    async def save_private_blob(
        self,
        lease: TurnLease,
        expected_session_version: int,
        form_id: str,
        encrypted_value: bytes,
        next_state: RouteDeckSession,
        events: Sequence[RouteDeckEvent],
        mutation: MutationCommit,
    ) -> SessionSnapshot:
        if lease != self.lease:
            raise SessionStoreError(SessionStoreErrorCode.LEASE_MISMATCH)
        snapshot = await self.load(lease.session_id)
        if snapshot.session_version != expected_session_version:
            raise SessionStoreError(SessionStoreErrorCode.VERSION_CONFLICT)
        self.private_blobs[form_id] = encrypted_value
        self.session = next_state
        self.events.extend(events)
        if self.claim is None:
            raise AssertionError("private form save requires its turn claim")
        self.mutations[lease.request_id] = MutationRecord(
            **mutation.model_dump(mode="python"),
            session_id=lease.session_id,
            request_id=lease.request_id,
            request_fingerprint=self.claim.request_fingerprint,
            committed_session_version=next_state.session_version,
            committed_projection_version=next_state.projection_version,
            committed_event_cursor=next_state.event_cursor,
        )
        return SessionSnapshot(state=next_state)

    async def load_private_blob(self, session_id: str, form_id: str) -> bytes | None:
        await self.load(session_id)
        return self.private_blobs.get(form_id)

    async def events_after(
        self,
        session_id: str,
        cursor: int,
        limit: int,
    ) -> EventPage:
        await self.load(session_id)
        selected = tuple(event for event in self.events if event.cursor > cursor)
        page = selected[:limit]
        return EventPage(
            events=page,
            next_cursor=page[-1].cursor if page else cursor,
            has_more=len(selected) > limit,
        )

    def commit_public_event(self, event_type: RouteDeckEventType) -> RouteDeckSession:
        if self.session is None:
            raise AssertionError("smoke session was not created")
        cursor = self.session.event_cursor + 1
        next_state = self.session.model_copy(
            update={
                "session_version": self.session.session_version + 1,
                "projection_version": self.session.projection_version + 1,
                "event_cursor": cursor,
            }
        )
        self.events.append(
            RouteDeckEvent(
                event_id=f"event-{cursor}",
                cursor=cursor,
                event_type=event_type,
                session_id=next_state.session_id,
                session_version=next_state.session_version,
                projection_version=next_state.projection_version,
                created_at=datetime(2029, 1, 1, tzinfo=UTC),
                payload=PublicEventPayload(status_code="ready"),
            )
        )
        self.session = next_state
        return next_state


class _SmokeClock:
    def now(self) -> datetime:
        return datetime(2029, 1, 1, tzinfo=UTC)


class SmokeRunner:
    def __init__(self, store: SmokeStore) -> None:
        self.store = store
        self.review_session_id: str | None = None
        self.clock = _SmokeClock()
        self.id_factory = lambda kind: f"{kind}-smoke-private-form"

    async def run(self, request: OperationRequest) -> OperationResult:
        state = self.store.commit_public_event(RouteDeckEventType.OPERATION_CHANGED)
        return OperationResult(
            disposition=OperationDisposition.REQUIRES_REVIEW,
            session_id=request.session_id,
            request_id=request.request_id,
            operation_id=request.operation_id,
            session_version=state.session_version,
            projection_version=state.projection_version,
            evidence=OperationEvidence(
                source=OperationSource.SURFACE,
                phases=(OperationPhase.RECEIVED, OperationPhase.REVIEW_STAGED),
                attempt_id="attempt-1",
                request_fingerprint="fingerprint-1",
            ),
            review=OperationReview(
                id="review-1",
                expires_at=datetime(2029, 1, 1, tzinfo=UTC) + timedelta(minutes=5),
            ),
        )

    async def accept_review(
        self,
        review_id: str,
        request_id: str,
        expected_session_version: int,
        *,
        session_id: str | None = None,
    ) -> OperationResult:
        assert review_id == "review-1"
        assert session_id is not None
        snapshot = await self.store.load(session_id)
        assert snapshot.session_version == expected_session_version
        self.review_session_id = session_id
        state = self.store.commit_public_event(RouteDeckEventType.OPERATION_CHANGED)
        return OperationResult(
            disposition=OperationDisposition.COMPLETED,
            session_id=session_id,
            request_id=request_id,
            operation_id="checkout.place_order",
            session_version=state.session_version,
            projection_version=state.projection_version,
            evidence=OperationEvidence(
                source=OperationSource.SURFACE,
                phases=(OperationPhase.RECEIVED, OperationPhase.COMPLETED),
                attempt_id="attempt-2",
                request_fingerprint="fingerprint-2",
            ),
            outcome="accepted",
        )

    async def reject_review(
        self,
        review_id: str,
        request_id: str,
        expected_session_version: int,
        *,
        session_id: str | None = None,
    ) -> OperationResult:
        del review_id, request_id, expected_session_version, session_id
        raise AssertionError("the vertical smoke accepts its review")


def _smoke_dependencies() -> tuple[RouteDeckDependencies, SmokeStore, SmokeRunner]:
    compiled = compile_medusa_app_spec()
    store = SmokeStore()
    runner = SmokeRunner(store)
    codec = SmokeCodec()

    def session_factory(session_id: str) -> RouteDeckSession:
        return create_medusa_session(
            session_id=session_id,
            market=BuyerMarket(
                region_handle="region-public",
                country_code="us",
                currency_code="usd",
                sales_channel_handle="channel-public",
            ),
        )

    dependencies = RouteDeckDependencies(
        app=compiled,
        runner=runner,  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        notifier=SmokeNotifier(),  # type: ignore[arg-type]
        projector=ProjectionProjector(compiled),
        private_form_codec=codec,
        session_factory=session_factory,
        sse=SseSettings(follow=False),
    )
    return dependencies, store, runner


def test_complete_generic_transport_and_medusa_mount_smoke() -> None:
    dependencies, store, runner = _smoke_dependencies()
    client = TestClient(create_medusa_app(routedeck=dependencies))

    created = client.post(
        "/api/routedeck/sessions",
        json={"request_id": "create-session-1"},
    )
    assert created.status_code == 201
    assert created.headers["cache-control"] == "private, no-store"
    assert created.json()["projection"]["graph_node"] == "buyer.home"
    assert "HttpOnly" in created.headers["set-cookie"]
    assert "SameSite=lax" in created.headers["set-cookie"]
    session_cookie = client.cookies["routedeck_guest"]
    assert session_cookie not in created.text
    replayed_creation = client.post(
        "/api/routedeck/sessions",
        json={"request_id": "create-session-1"},
    )
    assert replayed_creation.status_code == 201
    assert replayed_creation.headers["cache-control"] == "private, no-store"
    assert client.cookies["routedeck_guest"] == session_cookie
    assert replayed_creation.json() == created.json()

    snapshot = client.get("/api/routedeck/session")
    assert snapshot.status_code == 200
    assert snapshot.headers["cache-control"] == "private, no-store"
    assert snapshot.json()["projection"]["session_version"] == 1

    proposed = client.post(
        "/api/routedeck/dispatch",
        json={
            "request_id": "proposal-1",
            "expected_session_version": 1,
            "operation_id": "checkout.place_order",
            "arguments": {},
        },
    )
    assert proposed.status_code == 200
    assert proposed.headers["cache-control"] == "private, no-store"
    assert proposed.json()["disposition"] == "requires_review"
    assert "session_id" not in proposed.json()

    accepted = client.post(
        "/api/routedeck/reviews/review-1/accept",
        json={"request_id": "accept-1", "expected_session_version": 2},
    )
    assert accepted.status_code == 200
    assert accepted.headers["cache-control"] == "private, no-store"
    assert accepted.json()["disposition"] == "completed"
    assert runner.review_session_id == session_cookie

    forged = client.put(
        "/api/routedeck/private-forms/contact",
        json={
            "request_id": "private-form-1",
            "expected_session_version": 3,
            "value": {"email": "buyer@example.test"},
        },
    )
    assert forged.status_code == 404
    assert forged.headers["cache-control"] == "private, no-store"
    assert store.private_blobs == {}

    projection = client.get("/api/routedeck/session")
    assert projection.status_code == 200
    assert projection.headers["cache-control"] == "private, no-store"
    assert "buyer@example.test" not in projection.text
    inspection = client.get("/api/routedeck/inspect")
    assert inspection.status_code == 200
    assert inspection.headers["cache-control"] == "private, no-store"
    assert inspection.json()["current_node"] == "buyer.home"
    assert "session_id" not in inspection.text

    replay = client.get("/api/routedeck/events", params={"after": 0})
    assert replay.status_code == 200
    assert replay.headers["cache-control"] == "private, no-store, no-transform"
    assert replay.headers["content-type"].startswith("text/event-stream")
    assert [
        int(line.removeprefix("id: "))
        for line in replay.text.splitlines()
        if line.startswith("id: ")
    ] == [1, 2]
    assert session_cookie not in replay.text

    assert client.get("/api/medusa-agent/health").json() == {"status": "ok"}


def test_mutation_transport_rejects_simple_cross_origin_and_non_json_requests() -> None:
    text_dependencies, text_store, _runner = _smoke_dependencies()
    text_client = TestClient(create_medusa_app(routedeck=text_dependencies))

    text_plain = text_client.post(
        "/api/routedeck/sessions",
        content=json.dumps({"request_id": "csrf-text-plain"}),
        headers={
            "Content-Type": "text/plain",
            "Origin": "http://testserver",
        },
    )

    assert text_plain.status_code == 415
    assert text_store.session is None

    origin_dependencies, origin_store, _runner = _smoke_dependencies()
    origin_client = TestClient(create_medusa_app(routedeck=origin_dependencies))
    untrusted_origin = origin_client.post(
        "/api/routedeck/sessions",
        json={"request_id": "csrf-same-site"},
        headers={
            "Origin": "http://attacker.testserver",
            "Sec-Fetch-Site": "same-site",
        },
    )

    assert untrusted_origin.status_code == 403
    assert origin_store.session is None

    trusted_dependencies, trusted_store, _runner = _smoke_dependencies()
    trusted_client = TestClient(create_medusa_app(routedeck=trusted_dependencies))
    trusted_origin = trusted_client.post(
        "/api/routedeck/sessions",
        json={"request_id": "trusted-local-frontend"},
        headers={
            "Origin": "http://127.0.0.1:5198",
            "Sec-Fetch-Site": "same-site",
        },
    )

    assert trusted_origin.status_code == 201
    assert trusted_store.session is not None


def test_health_is_liveness_and_does_not_require_runtime_dependencies() -> None:
    client = TestClient(create_medusa_app())

    assert client.get("/api/medusa-agent/health").json() == {"status": "ok"}
    response = client.get("/api/medusa-agent/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_readiness_checks_runtime_store_agent_and_medusa_probe() -> None:
    dependencies, _, _ = _smoke_dependencies()
    probe = _SmokeReadinessProbe()
    client = TestClient(
        create_medusa_app(
            routedeck=dependencies,
            agent=_SmokeAgent(),
            readiness=probe,
        )
    )

    response = client.get("/api/medusa-agent/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert probe.calls == ["routedeck_store", "medusa"]


class _SmokeAgent:
    async def astream_events(self, *_args, **_kwargs):
        if False:
            yield {}


@dataclass
class _SmokeReadinessProbe:
    routedeck_store: bool = True
    medusa: bool = True
    calls: list[str] = field(default_factory=list)

    async def routedeck_store_ready(self) -> bool:
        self.calls.append("routedeck_store")
        return self.routedeck_store

    async def medusa_ready(self) -> bool:
        self.calls.append("medusa")
        return self.medusa


def test_session_initializer_failure_never_returns_a_usable_session() -> None:
    compiled = compile_medusa_app_spec()
    store = SmokeStore()

    def session_factory(session_id: str) -> RouteDeckSession:
        return create_medusa_session(
            session_id=session_id,
            market=BuyerMarket(
                region_handle="region-public",
                country_code="us",
                currency_code="usd",
                sales_channel_handle="channel-public",
            ),
        )

    async def fail_initializer(snapshot: SessionSnapshot) -> SessionSnapshot:
        del snapshot
        raise RuntimeError("private initializer detail")

    dependencies = RouteDeckDependencies(
        app=compiled,
        runner=SmokeRunner(store),  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        notifier=SmokeNotifier(),  # type: ignore[arg-type]
        projector=ProjectionProjector(compiled),
        private_form_codec=SmokeCodec(),
        session_factory=session_factory,
        session_initializer=fail_initializer,
        sse=SseSettings(follow=False),
    )
    client = TestClient(create_medusa_app(routedeck=dependencies))

    failed = client.post(
        "/api/routedeck/sessions",
        json={"request_id": "create-with-failed-initializer"},
    )
    replayed = client.post(
        "/api/routedeck/sessions",
        json={"request_id": "create-with-failed-initializer"},
    )

    assert failed.status_code == 500
    assert "private initializer detail" not in failed.text
    assert "routedeck_guest" not in client.cookies
    assert "set-cookie" not in failed.headers
    assert replayed.status_code == 500
    assert "set-cookie" not in replayed.headers
    assert len(store.creation_requests) == 1
    assert client.get("/api/routedeck/session").status_code == 404


def test_declared_empty_private_form_is_virtual_and_not_persisted() -> None:
    client, store = _private_form_transport()

    response = client.get("/api/routedeck/private-forms/form-public-1")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json() == {
        "form_id": "form-public-1",
        "revision": 0,
        "complete": False,
        "session_version": 1,
        "value": {},
    }
    assert store.private_blobs == {}
    assert store.session is not None
    assert store.session.private_state.drafts == ()

    contract = client.get("/api/routedeck/contract")
    assert contract.status_code == 200
    assert "private_form_binding" not in contract.text
    assert "shipping_address" not in contract.text


def test_forged_private_form_get_and_put_are_rejected_before_lease() -> None:
    client, store = _private_form_transport()

    fetched = client.get("/api/routedeck/private-forms/forged-form")
    saved = client.put(
        "/api/routedeck/private-forms/forged-form",
        json={
            "request_id": "forged-save",
            "expected_session_version": 1,
            "value": {"email": "buyer@example.com"},
        },
    )

    assert fetched.status_code == 404
    assert saved.status_code == 404
    assert fetched.json()["failure"]["code"] == "private_form_not_found"
    assert saved.json()["failure"]["code"] == "private_form_not_found"
    assert store.lease is None
    assert store.private_blobs == {}


def test_private_form_rejects_undeclared_top_level_fields_before_lease() -> None:
    client, store = _private_form_transport()

    response = client.put(
        "/api/routedeck/private-forms/form-public-1",
        json={
            "request_id": "invalid-field-save",
            "expected_session_version": 1,
            "value": {
                "email": "buyer@example.com",
                "is_admin": True,
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["failure"]["code"] == "private_form_fields_undeclared"
    assert store.lease is None
    assert store.private_blobs == {}


def test_first_private_form_save_persists_revision_one_then_reloads() -> None:
    client, store = _private_form_transport()

    saved = client.put(
        "/api/routedeck/private-forms/form-public-1",
        json={
            "request_id": "first-real-save",
            "expected_session_version": 1,
            "complete": True,
            "value": {
                "email": "buyer@example.com",
                "shipping_address": {"country_code": "gb"},
            },
        },
    )
    loaded = client.get("/api/routedeck/private-forms/form-public-1")
    replayed = client.put(
        "/api/routedeck/private-forms/form-public-1",
        json={
            "request_id": "first-real-save",
            "expected_session_version": 1,
            "complete": True,
            "value": {
                "email": "buyer@example.com",
                "shipping_address": {"country_code": "gb"},
            },
        },
    )

    assert saved.status_code == 200
    assert saved.headers["cache-control"] == "private, no-store"
    assert saved.json() == {
        "form_id": "form-public-1",
        "revision": 1,
        "complete": True,
        "session_version": 2,
        "projection_version": 1,
    }
    assert loaded.status_code == 200
    assert replayed.status_code == 200
    assert replayed.json() == saved.json()
    assert loaded.json() == {
        "form_id": "form-public-1",
        "revision": 1,
        "complete": True,
        "session_version": 2,
        "value": {
            "email": "buyer@example.com",
            "shipping_address": {"country_code": "gb"},
        },
    }
    assert b"buyer@example.com" not in store.private_blobs["form-public-1"]
    assert len(store.events) == 1
    private_event = store.events[0]
    assert private_event.event_type is RouteDeckEventType.PRIVATE_FORM_CHANGED
    assert private_event.session_version == 2
    assert private_event.payload.entity_handles == ()
    assert private_event.payload.details == ()
    assert "form-public-1" not in private_event.model_dump_json()
    assert "buyer@example.com" not in private_event.model_dump_json()


def _private_form_transport() -> tuple[TestClient, SmokeStore]:
    surface = SurfaceSpec(
        id="test.private_form",
        component="test.private_form",
        private_form_binding={
            "form_id_prop": "form_handle",
            "allowed_field_names": (
                "email",
                "shipping_address",
            ),
        },
        public_props_schema=FrozenJsonObject(
            {
                "type": "object",
                "properties": {
                    "form_handle": {"type": "string", "minLength": 1},
                },
                "required": ["form_handle"],
                "additionalProperties": False,
            }
        ),
    )
    node = NodeSpec(
        id="test.private_form",
        title="Private form",
        kind=NodeKind.WORKFLOW,
        route=RouteSpec(
            template="/private-form",
            deep_link_policy=DeepLinkPolicy.SHAREABLE,
        ),
        surfaces=SurfaceSlotsSpec(active=surface, form=(surface,)),
    )
    compiled = compile_app(
        ApplicationSpec(
            name="private-form-transport",
            entry_node=node.ref,
            features=(FeatureSpec(namespace="private-form", nodes=(node,)),),
        )
    )
    store = SmokeStore()

    def session_factory(session_id: str) -> RouteDeckSession:
        return create_session(
            app=compiled,
            session_id=session_id,
            private_state=PrivateSessionState(),
            public_state=PublicSessionState(
                surface_state=(
                    PublicSurfaceState(
                        surface_id=surface.id,
                        values=(
                            ClassifiedValue(
                                name="form_handle",
                                value=FrozenJson("form-public-1"),
                                classification=DataClassification.PUBLIC,
                            ),
                        ),
                    ),
                )
            ),
        )

    dependencies = RouteDeckDependencies(
        app=compiled,
        runner=SmokeRunner(store),  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        notifier=SmokeNotifier(),  # type: ignore[arg-type]
        projector=ProjectionProjector(compiled),
        private_form_codec=SmokeCodec(),
        session_factory=session_factory,
        sse=SseSettings(follow=False),
    )
    client = TestClient(create_medusa_app(routedeck=dependencies))
    created = client.post(
        "/api/routedeck/sessions",
        json={"request_id": "create-session-private-form"},
    )
    assert created.status_code == 201
    return client, store
