from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from routedeck_core.app import CompiledRouteDeckApp
from routedeck_core.contracts.failures import (
    FailureKind,
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
    OperationRequest,
    OperationSource,
)
from routedeck_core.contracts.projection import (
    FrozenJsonObject,
)
from routedeck_core.contracts.session import PrivateDraft
from routedeck_core.ports import RouteDeckSessionStore
from routedeck_core.ports.notifier import notify_event_wakeup
from routedeck_core.navigation.transactions import (
    NavigationRequest as CoreNavigationRequest,
    RouteDeckNavigationRunner,
)
from routedeck_core.state.aggregate import RouteDeckSessionAggregate
from routedeck_core.state.leases import TurnClaim, TurnOwnerKind
from routedeck_core.state.session import require_current_session
from routedeck_core.supervision import RouteDeckOperationRunner

from .dependencies import (
    GuestCookieSettings,
    RouteDeckDependencies,
    RouteDeckDependencyUnavailable,
    SensitiveCodec,
    SessionFactory,
    SessionInitializer,
    SessionProjector,
    SseSettings,
)
from .contracts import (
    DispatchRequest,
    NavigationRequestBody,
    PrivateFormWriteRequest,
    ReviewRequest,
    RouteDeckHttpProblem as _HttpProblem,
    SessionCreateRequest,
)
from .inspection import event_cursor as _event_cursor, inspection as _inspection
from .private_forms import (
    authorized_private_form as _authorized_private_form,
    encrypt_private_form as _encrypt_private_form,
    private_form_fingerprint as _private_form_fingerprint,
    private_form_replay_response as _private_form_replay_response,
    private_form_state as _private_form_state,
    require_allowed_private_form_fields as _require_allowed_private_form_fields,
)
from .responses import (
    PRIVATE_CACHE_CONTROL as _PRIVATE_CACHE_CONTROL,
    exception_response as _exception_response,
    operation_response as _operation_response,
    public_projection as _public_projection,
)
from .session_http import (
    authenticated_snapshot as _authenticated_snapshot,
    guest_session_id as _guest_session_id,
    initialize_session as _initialize_session,
    make_session as _make_session,
    project as _project,
    resolve_dependencies as _resolve_dependencies,
    session_creation_fingerprint as _session_creation_fingerprint,
    set_guest_cookie as _set_guest_cookie,
    validated_body as _validated_body,
)
from .sse import stream_events
from .security import (
    RouteDeckMutationPolicy,
    SameOriginMutationPolicy,
)


DependencyProvider = Callable[
    [Request],
    RouteDeckDependencies | Awaitable[RouteDeckDependencies],
]


def create_routedeck_router(
    *,
    app: CompiledRouteDeckApp,
    runner: RouteDeckOperationRunner,
    store: RouteDeckSessionStore,
    notifier: Any,
    projector: SessionProjector,
    private_form_codec: SensitiveCodec,
    session_factory: SessionFactory,
    navigation: RouteDeckNavigationRunner | None = None,
    session_initializer: SessionInitializer | None = None,
    cookie: GuestCookieSettings | None = None,
    sse: SseSettings | None = None,
    mutation_policy: RouteDeckMutationPolicy | None = None,
) -> APIRouter:
    """Build the product-neutral RouteDeck HTTP transport from injected ports."""

    dependencies = RouteDeckDependencies(
        app=app,
        runner=runner,
        store=store,
        notifier=notifier,
        projector=projector,
        private_form_codec=private_form_codec,
        session_factory=session_factory,
        navigation=navigation,
        session_initializer=session_initializer,
        cookie=cookie or GuestCookieSettings(),
        sse=sse or SseSettings(),
    )

    async def provide(_request: Request) -> RouteDeckDependencies:
        return dependencies

    return create_routedeck_router_from_provider(
        provide,
        mutation_policy=mutation_policy,
    )


def create_routedeck_router_from_provider(
    provider: DependencyProvider,
    *,
    mutation_policy: RouteDeckMutationPolicy | None = None,
) -> APIRouter:
    """Build a router whose application composition is resolved per request."""

    router = APIRouter(prefix="/api/routedeck", tags=["routedeck"])
    request_policy = mutation_policy or SameOriginMutationPolicy()

    @router.get("/contract")
    async def get_frontend_contract(request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            return JSONResponse(
                content={
                    "frontend_contract": dependencies.app.frontend_contract.model_dump(
                        mode="json"
                    )
                },
                headers={"Cache-Control": "no-cache"},
            )
        except Exception as error:
            return _exception_response(error, cache_control="no-cache")

    @router.post("/sessions", status_code=201)
    async def create_session(request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            body = await _validated_body(request, SessionCreateRequest, request_policy)
            session_id = secrets.token_urlsafe(32)
            session = await _make_session(dependencies.session_factory, session_id)
            if session.session_id != session_id:
                raise _HttpProblem(
                    500,
                    "session_identity_mismatch",
                    "The session could not be created.",
                    FailureKind.INTERNAL,
                    "session_creation",
                )
            snapshot = await dependencies.store.create_for_request(
                session,
                body.request_id,
                _session_creation_fingerprint(),
            )
            session_id = snapshot.session_id
            try:
                snapshot = await _initialize_session(
                    dependencies.session_initializer,
                    snapshot,
                )
            except Exception as error:
                return _exception_response(error)
            projection = _project(dependencies, snapshot)
            response = JSONResponse(
                status_code=201,
                content={"projection": _public_projection(projection)},
                headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
            )
            _set_guest_cookie(response, session_id, dependencies.cookie)
            return response
        except Exception as error:
            return _exception_response(error)

    @router.get("/session")
    async def get_session(request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            snapshot = await _authenticated_snapshot(request, dependencies)
            projection = _project(dependencies, snapshot)
            return JSONResponse(
                content={"projection": _public_projection(projection)},
                headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return _exception_response(error)

    @router.post("/dispatch")
    async def dispatch(request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            session_id = _guest_session_id(request, dependencies.cookie)
            body = await _validated_body(request, DispatchRequest, request_policy)
            try:
                operation_request = OperationRequest(
                    session_id=session_id,
                    request_id=body.request_id,
                    expected_session_version=body.expected_session_version,
                    operation_id=body.operation_id,
                    source=OperationSource.SURFACE,
                    arguments=FrozenJsonObject(body.arguments),
                )
            except (TypeError, ValueError, ValidationError) as error:
                raise _HttpProblem(
                    400,
                    "invalid_request",
                    "The request is invalid.",
                ) from error
            result = await dependencies.runner.run(operation_request)
            return _operation_response(result)
        except Exception as error:
            return _exception_response(error)

    @router.post("/navigation")
    async def navigate(request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            if dependencies.navigation is None:
                raise RouteDeckDependencyUnavailable(
                    "RouteDeck navigation transactions are not configured"
                )
            session_id = _guest_session_id(request, dependencies.cookie)
            body = await _validated_body(request, NavigationRequestBody, request_policy)
            snapshot = await dependencies.navigation.navigate(
                CoreNavigationRequest(
                    session_id=session_id,
                    request_id=body.request_id,
                    expected_session_version=body.expected_session_version,
                    intent=body.intent,
                )
            )
            projection = _project(dependencies, snapshot)
            return JSONResponse(
                content={"projection": _public_projection(projection)},
                headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return _exception_response(error)

    @router.post("/reviews/{review_id}/accept")
    async def accept_review(review_id: str, request: Request):
        return await _review_response(
            provider=provider,
            request=request,
            review_id=review_id,
            accept=True,
            mutation_policy=request_policy,
        )

    @router.post("/reviews/{review_id}/reject")
    async def reject_review(review_id: str, request: Request):
        return await _review_response(
            provider=provider,
            request=request,
            review_id=review_id,
            accept=False,
            mutation_policy=request_policy,
        )

    @router.get("/events")
    async def events(request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            snapshot = await _authenticated_snapshot(request, dependencies)
            after_cursor = _event_cursor(request)
            first_page = await dependencies.store.events_after(
                snapshot.session_id,
                after_cursor,
                dependencies.sse.replay_batch_size,
            )
            body = stream_events(
                session_id=snapshot.session_id,
                after_cursor=after_cursor,
                store=dependencies.store,
                notifier=dependencies.notifier,
                settings=dependencies.sse,
                initial_page=first_page,
            )
            return StreamingResponse(
                body,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "private, no-store, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        except Exception as error:
            return _exception_response(error)

    @router.get("/private-forms/{form_id}")
    async def get_private_form(form_id: str, request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            snapshot = await _authenticated_snapshot(request, dependencies)
            binding = _authorized_private_form(
                dependencies,
                snapshot,
                form_id,
            )
            draft, encrypted, value = await _private_form_state(
                dependencies=dependencies,
                snapshot=snapshot,
                form_id=form_id,
                binding=binding,
            )
            if draft is None and encrypted is None:
                return JSONResponse(
                    content={
                        "form_id": form_id,
                        "revision": 0,
                        "complete": False,
                        "session_version": snapshot.session_version,
                        "value": {},
                    },
                    headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
                )
            if draft is None or value is None:
                raise RuntimeError("validated private form state is incomplete")
            return JSONResponse(
                content={
                    "form_id": form_id,
                    "revision": draft.revision,
                    "complete": draft.complete,
                    "session_version": snapshot.session_version,
                    "value": value,
                },
                headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return _exception_response(error)

    @router.put("/private-forms/{form_id}")
    async def put_private_form(form_id: str, request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            session_id = _guest_session_id(request, dependencies.cookie)
            body = await _validated_body(
                request,
                PrivateFormWriteRequest,
                request_policy,
            )
            try:
                FrozenJsonObject(body.value)
            except (TypeError, ValueError) as error:
                raise _HttpProblem(
                    400,
                    "invalid_request",
                    "The request is invalid.",
                ) from error
            fingerprint = _private_form_fingerprint(form_id, body)
            recorded = await dependencies.store.find_mutation(
                session_id,
                body.request_id,
            )
            if recorded is not None:
                return _private_form_replay_response(
                    recorded,
                    fingerprint=fingerprint,
                    form_id=form_id,
                )
            snapshot = await dependencies.store.load(session_id)
            require_current_session(dependencies.app, snapshot.state)
            binding = _authorized_private_form(
                dependencies,
                snapshot,
                form_id,
            )
            _require_allowed_private_form_fields(
                binding,
                tuple(body.value),
                stored=False,
            )
            current_draft, _encrypted, _value = await _private_form_state(
                dependencies=dependencies,
                snapshot=snapshot,
                form_id=form_id,
                binding=binding,
            )
            revision = current_draft.revision + 1 if current_draft else 1
            draft = PrivateDraft(
                form_id=form_id,
                field_names=tuple(sorted(body.value)),
                revision=revision,
                complete=body.complete,
            )
            next_state = (
                RouteDeckSessionAggregate(snapshot.state)
                .store_private_draft(draft)
                .record_public_events(1)
                .commit()
            )
            event = RouteDeckEvent(
                event_id=dependencies.runner.id_factory("event"),
                cursor=next_state.event_cursor,
                event_type=RouteDeckEventType.PRIVATE_FORM_CHANGED,
                session_id=next_state.session_id,
                session_version=next_state.session_version,
                projection_version=next_state.projection_version,
                created_at=dependencies.runner.clock.now(),
                payload=PublicEventPayload(
                    node_id=next_state.current.node_id,
                    request_id=body.request_id,
                    status_code=next_state.public_state.status_code,
                ),
            )
            encrypted = _encrypt_private_form(
                dependencies.private_form_codec,
                body.value,
            )
            lease = await dependencies.store.acquire_turn(
                TurnClaim(
                    session_id=snapshot.session_id,
                    expected_session_version=body.expected_session_version,
                    request_id=body.request_id,
                    request_fingerprint=fingerprint,
                    owner_kind=TurnOwnerKind.SURFACE,
                )
            )
            try:
                saved = await dependencies.store.save_private_blob(
                    lease,
                    body.expected_session_version,
                    form_id,
                    encrypted,
                    next_state,
                    (event,),
                    MutationCommit(
                        kind=MutationKind.PRIVATE_FORM,
                        status=MutationStatus.COMPLETED,
                        result=FrozenJsonObject(
                            {
                                "complete": body.complete,
                                "form_id": form_id,
                                "revision": revision,
                            }
                        ),
                    ),
                )
            finally:
                await dependencies.store.release_turn(lease)
            await notify_event_wakeup(dependencies.notifier, saved.session_id, (event,))
            return JSONResponse(
                content={
                    "form_id": form_id,
                    "revision": revision,
                    "complete": body.complete,
                    "session_version": saved.session_version,
                    "projection_version": saved.projection_version,
                },
                headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return _exception_response(error)

    @router.get("/inspect")
    async def inspect_session(request: Request):
        try:
            dependencies = await _resolve_dependencies(provider, request)
            snapshot = await _authenticated_snapshot(request, dependencies)
            projection = _project(dependencies, snapshot)
            return JSONResponse(
                content=_inspection(dependencies, snapshot, projection),
                headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return _exception_response(error)

    return router


async def _review_response(
    *,
    provider: DependencyProvider,
    request: Request,
    review_id: str,
    accept: bool,
    mutation_policy: RouteDeckMutationPolicy,
):
    try:
        dependencies = await _resolve_dependencies(provider, request)
        session_id = _guest_session_id(request, dependencies.cookie)
        body = await _validated_body(request, ReviewRequest, mutation_policy)
        method = (
            dependencies.runner.accept_review
            if accept
            else dependencies.runner.reject_review
        )
        result = await method(
            review_id,
            request_id=body.request_id,
            expected_session_version=body.expected_session_version,
            session_id=session_id,
        )
        return _operation_response(result)
    except Exception as error:
        return _exception_response(error)


__all__ = [
    "DispatchRequest",
    "PrivateFormWriteRequest",
    "ReviewRequest",
    "create_routedeck_router",
    "create_routedeck_router_from_provider",
]
