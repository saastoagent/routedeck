from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from routedeck_core.contracts.events import (
    PublicEventPayload,
    RouteDeckEvent,
    RouteDeckEventType,
)
from routedeck_core.contracts.mutations import (
    MutationCommit,
    MutationKind,
    MutationStatus,
)
from routedeck_core.contracts.projection import FrozenJsonObject
from routedeck_core.contracts.session import PrivateDraft
from routedeck_core.ports.notifier import notify_event_wakeup
from routedeck_core.state.aggregate import RouteDeckSessionAggregate
from routedeck_core.state.leases import TurnClaim, TurnOwnerKind
from routedeck_core.state.session import require_current_session

from ..contracts import PrivateFormWriteRequest, RouteDeckHttpProblem
from ..private_forms import (
    authorized_private_form,
    encrypt_private_form,
    private_form_fingerprint,
    private_form_replay_response,
    private_form_state,
    require_allowed_private_form_fields,
)
from ..responses import PRIVATE_CACHE_CONTROL, exception_response
from ..security import RouteDeckMutationPolicy
from ..session_http import (
    authenticated_snapshot,
    guest_session_id,
    resolve_dependencies,
    validated_body,
)
from . import DependencyProvider


def create_private_form_routes(
    provider: DependencyProvider,
    mutation_policy: RouteDeckMutationPolicy,
) -> APIRouter:
    router = APIRouter()

    @router.get("/private-forms/{form_id}")
    async def get_private_form(form_id: str, request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            snapshot = await authenticated_snapshot(request, dependencies)
            binding = authorized_private_form(
                dependencies,
                snapshot,
                form_id,
            )
            draft, encrypted, value = await private_form_state(
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
                    headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
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
                headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return exception_response(error)

    @router.put("/private-forms/{form_id}")
    async def put_private_form(form_id: str, request: Request):
        try:
            dependencies = await resolve_dependencies(provider, request)
            session_id = guest_session_id(request, dependencies.cookie)
            body = await validated_body(
                request,
                PrivateFormWriteRequest,
                mutation_policy,
            )
            try:
                FrozenJsonObject(body.value)
            except (TypeError, ValueError) as error:
                raise RouteDeckHttpProblem(
                    400,
                    "invalid_request",
                    "The request is invalid.",
                ) from error
            fingerprint = private_form_fingerprint(form_id, body)
            recorded = await dependencies.store.find_mutation(
                session_id,
                body.request_id,
            )
            if recorded is not None:
                return private_form_replay_response(
                    recorded,
                    fingerprint=fingerprint,
                    form_id=form_id,
                )
            snapshot = await dependencies.store.load(session_id)
            require_current_session(dependencies.app, snapshot.state)
            binding = authorized_private_form(
                dependencies,
                snapshot,
                form_id,
            )
            require_allowed_private_form_fields(
                binding,
                tuple(body.value),
                stored=False,
            )
            current_draft, _encrypted, _value = await private_form_state(
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
            encrypted = encrypt_private_form(
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
            await notify_event_wakeup(
                dependencies.notifier,
                saved.session_id,
                (event,),
            )
            return JSONResponse(
                content={
                    "form_id": form_id,
                    "revision": revision,
                    "complete": body.complete,
                    "session_version": saved.session_version,
                    "projection_version": saved.projection_version,
                },
                headers={"Cache-Control": PRIVATE_CACHE_CONTROL},
            )
        except Exception as error:
            return exception_response(error)

    return router


__all__ = ["create_private_form_routes"]
