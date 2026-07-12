from __future__ import annotations

import hashlib
import inspect
import json
import secrets
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from routedeck_core.app import CompiledRouteDeckApp
from routedeck_core.contracts.failures import (
    FailureKind,
    RouteDeckFailure,
)
from routedeck_core.contracts.events import (
    CanonicalRouteDeckEvent,
    PublicEventPayload,
    RouteDeckEventKind,
)
from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationRecord,
    MutationStatus,
)
from routedeck_core.contracts.operations import (
    OperationDisposition,
    OperationRequest,
    OperationResult,
    OperationSource,
)
from routedeck_core.contracts.projection import (
    FrozenJsonObject,
    ProjectedSurface,
    PublicProjection,
)
from routedeck_core.contracts.session import PrivateDraft, SessionSnapshot
from routedeck_core.contracts.surfaces import PrivateFormBindingSpec
from routedeck_core.ports import RouteDeckSessionStore, SessionStoreError
from routedeck_core.ports.notifier import notify_event_wakeup
from routedeck_core.navigation.transactions import (
    NavigationIntent,
    NavigationRequest as CoreNavigationRequest,
    NavigationTransactionError,
    RouteDeckNavigationRunner,
)
from routedeck_core.state.leases import TurnClaim, TurnOwnerKind
from routedeck_core.state.reducer import (
    PrivateDraftStored,
    PublicEventsRecorded,
    reduce_session_batch,
)
from routedeck_core.state.session import require_compatible_session
from routedeck_core.supervision import RouteDeckOperationRunner
from routedeck_core.validation import RouteDeckValidationError

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
from .sse import stream_events
from .security import (
    RouteDeckMutationPolicy,
    RouteDeckMutationRejected,
    SameOriginMutationPolicy,
)


_PRIVATE_CACHE_CONTROL = "private, no-store"


class _RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DispatchRequest(_RequestModel):
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    operation_id: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class SessionCreateRequest(_RequestModel):
    request_id: str = Field(min_length=1)


class ReviewRequest(_RequestModel):
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)


class PrivateFormWriteRequest(_RequestModel):
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    value: dict[str, Any]
    complete: bool = True


class NavigationRequestBody(_RequestModel):
    request_id: str = Field(min_length=1)
    expected_session_version: int = Field(ge=0)
    intent: NavigationIntent


@dataclass(frozen=True)
class _HttpProblem(Exception):
    status_code: int
    code: str
    public_message: str
    kind: FailureKind = FailureKind.CONTRACT
    phase: str = "http_transport"


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
            require_compatible_session(dependencies.app, snapshot.state)
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
            next_state = reduce_session_batch(
                snapshot.state,
                (
                    PrivateDraftStored(draft=draft),
                    PublicEventsRecorded(count=1),
                ),
            )
            event = CanonicalRouteDeckEvent(
                event_id=dependencies.runner.id_factory("event"),
                cursor=next_state.event_cursor,
                event_type=RouteDeckEventKind.PRIVATE_FORM_CHANGED,
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


async def _resolve_dependencies(
    provider: DependencyProvider,
    request: Request,
) -> RouteDeckDependencies:
    dependencies = provider(request)
    if inspect.isawaitable(dependencies):
        dependencies = await dependencies
    if not isinstance(dependencies, RouteDeckDependencies):
        raise RouteDeckDependencyUnavailable("RouteDeck runtime is not configured")
    return dependencies


async def _make_session(
    factory: SessionFactory,
    session_id: str,
):
    session = factory(session_id)
    return await session if inspect.isawaitable(session) else session


async def _initialize_session(
    initializer: SessionInitializer | None,
    snapshot: SessionSnapshot,
) -> SessionSnapshot:
    if initializer is None:
        return snapshot
    initialized = initializer(snapshot)
    if inspect.isawaitable(initialized):
        initialized = await initialized
    if not isinstance(initialized, SessionSnapshot):
        raise _HttpProblem(
            500,
            "session_initializer_invalid",
            "The session could not be initialized.",
            FailureKind.INTERNAL,
            "session_creation",
        )
    if (
        initialized.state.session_id != snapshot.state.session_id
        or initialized.session_version < snapshot.session_version
    ):
        raise _HttpProblem(
            500,
            "session_initializer_invalid",
            "The session could not be initialized.",
            FailureKind.INTERNAL,
            "session_creation",
        )
    return initialized


async def _validated_body(
    request: Request,
    model: type[_RequestModel],
    mutation_policy: RouteDeckMutationPolicy,
):
    try:
        mutation_policy.authorize(request)
    except RouteDeckMutationRejected as error:
        raise _HttpProblem(
            403,
            "mutation_origin_rejected",
            "The mutation request origin is not authorized.",
            FailureKind.CONTRACT,
            "request_security",
        ) from error
    content_type = request.headers.get("content-type", "")
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type != "application/json":
        raise _HttpProblem(
            415,
            "unsupported_media_type",
            "RouteDeck mutations require Content-Type: application/json.",
        )
    try:
        value = await request.json()
        return model.model_validate(value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
        raise _HttpProblem(400, "invalid_request", "The request is invalid.") from error


def _guest_session_id(request: Request, settings: GuestCookieSettings) -> str:
    session_id = request.cookies.get(settings.name)
    if not session_id:
        raise _HttpProblem(
            404,
            "session_not_found",
            "No RouteDeck guest session is available.",
        )
    if len(session_id) > 512:
        raise _HttpProblem(400, "invalid_session_cookie", "The session is invalid.")
    return session_id


async def _authenticated_snapshot(
    request: Request,
    dependencies: RouteDeckDependencies,
) -> SessionSnapshot:
    session_id = _guest_session_id(request, dependencies.cookie)
    snapshot = await dependencies.store.load(session_id)
    require_compatible_session(dependencies.app, snapshot.state)
    return snapshot


def _project(
    dependencies: RouteDeckDependencies,
    snapshot: SessionSnapshot,
) -> PublicProjection:
    require_compatible_session(dependencies.app, snapshot.state)
    return dependencies.projector.project(snapshot.state)


def _public_projection(projection: PublicProjection) -> dict[str, Any]:
    value = projection.model_dump(mode="json")
    value["graph_node"] = projection.current.node_id
    return value


def _set_guest_cookie(
    response: JSONResponse,
    session_id: str,
    settings: GuestCookieSettings,
) -> None:
    response.set_cookie(
        key=settings.name,
        value=session_id,
        httponly=True,
        secure=settings.secure,
        samesite="lax",
        path=settings.path,
    )


def _public_operation_result(result: OperationResult) -> dict[str, Any]:
    return result.model_dump(mode="json", exclude={"session_id"})


def _operation_response(result: OperationResult) -> JSONResponse:
    status_code = _operation_status(result)
    return JSONResponse(
        status_code=status_code,
        content=_public_operation_result(result),
        headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
    )


def _operation_status(result: OperationResult) -> int:
    if result.disposition is OperationDisposition.NEEDS_INPUT:
        return 422
    if result.disposition is OperationDisposition.PENDING:
        return 202
    failure = result.failure
    if failure is None:
        return 200
    if failure.code in {
        "operation_not_available",
        "review_not_found",
        "route_not_found",
        "session_not_found",
    }:
        return 404
    if failure.code == "session_expired":
        return 410
    if failure.kind is FailureKind.CONTRACT:
        return 400
    if failure.kind in {
        FailureKind.STATE_CONFLICT,
        FailureKind.GUARD,
        FailureKind.REVIEW,
        FailureKind.BUSINESS,
        FailureKind.EXTERNAL_OUTCOME_UNKNOWN,
    }:
        return 409
    if failure.kind in {
        FailureKind.CONTEXT_PROVIDER,
        FailureKind.TRANSPORT,
        FailureKind.PROVIDER_PROTOCOL,
        FailureKind.PERSISTENCE,
    }:
        return 503
    return 500


def _private_draft(snapshot: SessionSnapshot, form_id: str) -> PrivateDraft | None:
    return next(
        (
            draft
            for draft in snapshot.state.private_state.drafts
            if draft.form_id == form_id
        ),
        None,
    )


def _authorized_private_form(
    dependencies: RouteDeckDependencies,
    snapshot: SessionSnapshot,
    form_id: str,
) -> PrivateFormBindingSpec:
    projection = _project(dependencies, snapshot)
    node = next(
        (
            candidate
            for candidate in dependencies.app.spec.nodes
            if candidate.id == snapshot.state.current.node_id
        ),
        None,
    )
    if node is None:
        raise _HttpProblem(
            500,
            "private_form_binding_invalid",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_authorization",
        )
    surface_specs = {
        surface.id: surface for surface in node.surfaces.declared_surfaces()
    }
    matches: list[PrivateFormBindingSpec] = []
    seen_surface_ids: set[str] = set()
    for surface in _projected_surfaces(projection):
        if surface.surface_id in seen_surface_ids:
            continue
        seen_surface_ids.add(surface.surface_id)
        spec = surface_specs.get(surface.surface_id)
        binding = spec.private_form_binding if spec is not None else None
        if binding is None:
            continue
        props = {value.name: value.value.to_python() for value in surface.props}
        projected_form_id = props.get(binding.form_id_prop)
        if not isinstance(projected_form_id, str) or not projected_form_id:
            raise _HttpProblem(
                500,
                "private_form_binding_invalid",
                "The private form could not be loaded.",
                FailureKind.INTERNAL,
                "private_form_authorization",
            )
        if projected_form_id == form_id:
            matches.append(binding)
    if not matches:
        raise _HttpProblem(
            404,
            "private_form_not_found",
            "That private form is unavailable.",
        )
    if len(matches) != 1:
        raise _HttpProblem(
            500,
            "private_form_binding_invalid",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_authorization",
        )
    return matches[0]


def _projected_surfaces(projection: PublicProjection) -> tuple[ProjectedSurface, ...]:
    slots = projection.surfaces
    return (
        slots.active,
        *slots.frame,
        *slots.peer,
        *slots.detail,
        *slots.form,
        *slots.review,
        *slots.status,
        *slots.error,
        *slots.diagnostic,
    )


async def _private_form_state(
    *,
    dependencies: RouteDeckDependencies,
    snapshot: SessionSnapshot,
    form_id: str,
    binding: PrivateFormBindingSpec,
) -> tuple[PrivateDraft | None, bytes | None, dict[str, Any] | None]:
    draft = _private_draft(snapshot, form_id)
    encrypted = await dependencies.store.load_private_blob(
        snapshot.session_id,
        form_id,
    )
    if (draft is None) != (encrypted is None):
        raise _HttpProblem(
            500,
            "private_form_state_mismatch",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_load",
        )
    if draft is None or encrypted is None:
        return draft, encrypted, None
    value = _decrypt_private_form(dependencies.private_form_codec, encrypted)
    if tuple(sorted(value)) != draft.field_names:
        raise _HttpProblem(
            500,
            "private_form_schema_mismatch",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_load",
        )
    _require_allowed_private_form_fields(
        binding,
        draft.field_names,
        stored=True,
    )
    return draft, encrypted, value


def _require_allowed_private_form_fields(
    binding: PrivateFormBindingSpec,
    field_names: tuple[str, ...],
    *,
    stored: bool,
) -> None:
    unexpected = set(field_names).difference(binding.allowed_field_names)
    if not unexpected:
        return
    raise _HttpProblem(
        500 if stored else 400,
        "private_form_schema_mismatch" if stored else "private_form_fields_undeclared",
        "The private form could not be loaded."
        if stored
        else "The private form contains undeclared fields.",
        FailureKind.INTERNAL if stored else FailureKind.CONTRACT,
        "private_form_load" if stored else "private_form_validation",
    )


def _private_form_fingerprint(
    form_id: str,
    request: PrivateFormWriteRequest,
) -> str:
    canonical = json.dumps(
        {
            "complete": request.complete,
            "form_id": form_id,
            "value": request.value,
        },
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _session_creation_fingerprint() -> str:
    return hashlib.sha256(b"routedeck.session-creation.v1").hexdigest()


def _private_form_replay_response(
    record: MutationRecord,
    *,
    fingerprint: str,
    form_id: str,
) -> JSONResponse:
    if (
        record.kind is not MutationKind.PRIVATE_FORM
        or record.request_fingerprint != fingerprint
    ):
        raise _HttpProblem(
            409,
            "request_id_reused",
            "This request ID was already used for another mutation.",
            FailureKind.STATE_CONFLICT,
            "mutation_replay",
        )
    if record.status is not MutationStatus.COMPLETED:
        raise _HttpProblem(
            500,
            "mutation_record_invalid",
            "The private form result could not be replayed.",
            FailureKind.INTERNAL,
            "mutation_replay",
        )
    result = record.result.to_dict()
    if (
        set(result) != {"complete", "form_id", "revision"}
        or result.get("form_id") != form_id
        or not isinstance(result.get("complete"), bool)
        or not isinstance(result.get("revision"), int)
        or isinstance(result.get("revision"), bool)
    ):
        raise _HttpProblem(
            500,
            "mutation_record_invalid",
            "The private form result could not be replayed.",
            FailureKind.INTERNAL,
            "mutation_replay",
        )
    return JSONResponse(
        content={
            **result,
            "session_version": record.committed_session_version,
            "projection_version": record.committed_projection_version,
        },
        headers={"Cache-Control": _PRIVATE_CACHE_CONTROL},
    )


def _encrypt_private_form(
    codec: SensitiveCodec,
    value: Mapping[str, Any],
) -> bytes:
    try:
        plaintext = json.dumps(
            dict(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return codec.encrypt(plaintext)
    except Exception as error:
        raise _HttpProblem(
            500,
            "private_form_encryption_failed",
            "The private form could not be saved.",
            FailureKind.INTERNAL,
            "private_form_encrypt",
        ) from error


def _decrypt_private_form(
    codec: SensitiveCodec,
    encrypted: bytes,
) -> dict[str, Any]:
    try:
        value = json.loads(codec.decrypt(encrypted))
    except Exception as error:
        raise _HttpProblem(
            500,
            "private_form_decryption_failed",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_decrypt",
        ) from error
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise _HttpProblem(
            500,
            "private_form_payload_invalid",
            "The private form could not be loaded.",
            FailureKind.INTERNAL,
            "private_form_decrypt",
        )
    return value


def _event_cursor(request: Request) -> int:
    after_values = request.query_params.getlist("after")
    if len(after_values) > 1:
        raise _HttpProblem(
            400, "conflicting_event_cursor", "The event cursor is invalid."
        )
    header_value = request.headers.get("last-event-id")
    after = _parse_cursor(after_values[0], "after") if after_values else None
    header = (
        _parse_cursor(header_value, "Last-Event-ID")
        if header_value is not None
        else None
    )
    if after is not None and header is not None and after != header:
        raise _HttpProblem(
            400,
            "conflicting_event_cursor",
            "Last-Event-ID and after must match.",
        )
    return header if header is not None else (after if after is not None else 0)


def _parse_cursor(value: str, field_name: str) -> int:
    try:
        cursor = int(value)
    except (TypeError, ValueError) as error:
        raise _HttpProblem(
            400,
            "invalid_event_cursor",
            f"{field_name} must be a non-negative integer.",
        ) from error
    if cursor < 0 or str(cursor) != value.strip():
        raise _HttpProblem(
            400,
            "invalid_event_cursor",
            f"{field_name} must be a non-negative integer.",
        )
    return cursor


def _inspection(
    dependencies: RouteDeckDependencies,
    snapshot: SessionSnapshot,
    projection: PublicProjection,
) -> dict[str, Any]:
    current_node_id = projection.current.node_id
    node = next(
        node for node in dependencies.app.spec.nodes if node.id == current_node_id
    )
    legal_ids = set(projection.legal_operation_ids)
    reachable = sorted(
        {
            transition.target.id
            for transition in dependencies.app.spec.transitions
            if transition.source.id == current_node_id
        }
    )
    route_traces = [
        {
            "source": transition.source.id,
            "operation_id": transition.operation.id,
            "outcome": transition.outcome,
            "target": transition.target.id,
        }
        for transition in dependencies.app.spec.transitions
        if transition.source.id == current_node_id
    ]
    return {
        "current_node": current_node_id,
        "reachable_nodes": reachable,
        "legal_operations": [
            operation.model_dump(mode="json")
            for operation in projection.legal_operations
        ],
        "blocked_operations": [
            {
                "operation_id": operation.id,
                "reason": "not_legal_in_current_state",
            }
            for operation in node.operations
            if operation.id not in legal_ids
        ],
        "guard_explanations": [guard.id for guard in node.guards],
        "capabilities": [
            capability.model_dump(mode="json") for capability in node.capabilities
        ],
        "surfaces": projection.surfaces.model_dump(mode="json"),
        "route_traces": route_traces,
        "diagnostics": {
            **projection.diagnostics.model_dump(mode="json"),
            "session_version": snapshot.session_version,
            "projection_version": snapshot.projection_version,
            "event_cursor": snapshot.event_cursor,
        },
    }


def _exception_response(
    error: Exception,
    *,
    cache_control: str | None = _PRIVATE_CACHE_CONTROL,
) -> JSONResponse:
    status_code, failure = _failure_for_exception(error)
    headers = {"Cache-Control": cache_control} if cache_control else None
    return JSONResponse(
        status_code=status_code,
        content={"failure": failure.model_dump(mode="json")},
        headers=headers,
    )


def _failure_for_exception(error: Exception) -> tuple[int, RouteDeckFailure]:
    if isinstance(error, _HttpProblem):
        return error.status_code, _transport_failure(
            kind=error.kind,
            code=error.code,
            phase=error.phase,
            public_message=error.public_message,
        )
    if isinstance(error, RouteDeckDependencyUnavailable):
        return 503, _transport_failure(
            kind=FailureKind.TRANSPORT,
            code="dependency_unavailable",
            phase="dependency_resolution",
            public_message="The RouteDeck runtime is unavailable.",
        )
    if isinstance(error, SessionStoreError):
        code = error.code.value
        if code == "session_not_found":
            status = 404
        elif code == "session_expired":
            status = 410
        elif code in {
            "session_already_exists",
            "version_conflict",
            "request_id_reused",
            "operation_in_progress",
            "lease_mismatch",
            "execution_already_claimed",
            "review_already_resolved",
            "result_mismatch",
            "session_upgrade_required",
        }:
            status = 409
        elif code == "persistence_failure":
            status = 503
        else:
            status = 500
        kind = FailureKind.STATE_CONFLICT if status == 409 else FailureKind.PERSISTENCE
        return status, _transport_failure(
            kind=kind,
            code=code,
            phase="session_store",
            public_message="The RouteDeck session request could not be completed.",
        )
    if isinstance(error, NavigationTransactionError):
        conflict_codes = {
            "version_conflict",
            "history_path_mismatch",
        }
        return (
            409 if error.code in conflict_codes else 400,
            _transport_failure(
                kind=(
                    FailureKind.STATE_CONFLICT
                    if error.code in conflict_codes
                    else FailureKind.CONTRACT
                ),
                code=error.code,
                phase="navigation",
                public_message=error.public_message,
            ),
        )
    if (
        isinstance(error, RouteDeckValidationError)
        and str(error) == "session_upgrade_required"
    ):
        return 409, _transport_failure(
            kind=FailureKind.STATE_CONFLICT,
            code="session_upgrade_required",
            phase="session_validation",
            public_message="This session requires an application upgrade.",
        )
    return 500, _transport_failure(
        kind=FailureKind.INTERNAL,
        code="internal_invariant",
        phase="http_transport",
        public_message="The RouteDeck request could not be completed.",
    )


def _transport_failure(
    *,
    kind: FailureKind,
    code: str,
    phase: str,
    public_message: str,
) -> RouteDeckFailure:
    return RouteDeckFailure(
        kind=kind,
        code=code,
        phase=phase,
        correlation_id=secrets.token_urlsafe(12),
        public_message=public_message,
    )


__all__ = [
    "DispatchRequest",
    "PrivateFormWriteRequest",
    "ReviewRequest",
    "create_routedeck_router",
    "create_routedeck_router_from_provider",
]
