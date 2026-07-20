from __future__ import annotations

import hashlib
import inspect
import json
from typing import TypeVar

from dataclasses import dataclass

from fastapi import Request, Response
from pydantic import ValidationError

from routedeck_core.contracts.failures import FailureKind
from routedeck_core.contracts.projection import PublicProjection
from routedeck_core.contracts.session import SessionSnapshot
from routedeck_core.state.session import require_current_session

from .contracts import RouteDeckHttpProblem, RouteDeckRequestModel
from .dependencies import (
    GuestCookieSettings,
    RouteDeckDependencies,
    RouteDeckDependencyUnavailable,
    RouteDeckSessionSelector,
    SessionFactory,
    SessionInitializer,
)
from .security import RouteDeckMutationPolicy, RouteDeckMutationRejected


RequestModelT = TypeVar("RequestModelT", bound=RouteDeckRequestModel)


async def resolve_dependencies(provider, request: Request) -> RouteDeckDependencies:
    dependencies = provider(request)
    if inspect.isawaitable(dependencies):
        dependencies = await dependencies
    if not isinstance(dependencies, RouteDeckDependencies):
        raise RouteDeckDependencyUnavailable("RouteDeck runtime is not configured")
    return dependencies


async def make_session(factory: SessionFactory, session_id: str):
    session = factory(session_id)
    return await session if inspect.isawaitable(session) else session


async def initialize_session(
    initializer: SessionInitializer | None,
    snapshot: SessionSnapshot,
) -> SessionSnapshot:
    if initializer is None:
        return snapshot
    initialized = initializer(snapshot)
    if inspect.isawaitable(initialized):
        initialized = await initialized
    if not isinstance(initialized, SessionSnapshot):
        raise RouteDeckHttpProblem(
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
        raise RouteDeckHttpProblem(
            500,
            "session_initializer_invalid",
            "The session could not be initialized.",
            FailureKind.INTERNAL,
            "session_creation",
        )
    return initialized


async def validated_body(
    request: Request,
    model: type[RequestModelT],
    mutation_policy: RouteDeckMutationPolicy,
) -> RequestModelT:
    try:
        mutation_policy.authorize(request)
    except RouteDeckMutationRejected as error:
        raise RouteDeckHttpProblem(
            403,
            "mutation_origin_rejected",
            "The mutation request origin is not authorized.",
            FailureKind.CONTRACT,
            "request_security",
        ) from error
    content_type = request.headers.get("content-type", "")
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type != "application/json":
        raise RouteDeckHttpProblem(
            415,
            "unsupported_media_type",
            "RouteDeck mutations require Content-Type: application/json.",
        )
    try:
        value = await request.json()
        return model.model_validate(value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
        raise RouteDeckHttpProblem(
            400,
            "invalid_request",
            "The request is invalid.",
        ) from error


@dataclass(frozen=True)
class GuestCookieSessionSelector:
    settings: GuestCookieSettings

    async def selected_session_id(self, request: Request) -> str:
        session_id = request.cookies.get(self.settings.name)
        if not session_id:
            raise RouteDeckHttpProblem(
                404,
                "session_not_found",
                "No RouteDeck guest session is available.",
            )
        return session_id

    def attach_created_session(
        self,
        response: Response,
        session_id: str,
    ) -> None:
        response.set_cookie(
            key=self.settings.name,
            value=session_id,
            httponly=True,
            secure=self.settings.secure,
            samesite="lax",
            path=self.settings.path,
        )


async def selected_session_id(
    request: Request,
    selector: RouteDeckSessionSelector,
) -> str:
    session_id = await selector.selected_session_id(request)
    if not isinstance(session_id, str) or not session_id or len(session_id) > 512:
        raise RouteDeckHttpProblem(
            500,
            "session_selection_invalid",
            "The selected session is unavailable.",
            FailureKind.INTERNAL,
            "session_selection",
        )
    return session_id


async def authenticated_snapshot(
    request: Request,
    dependencies: RouteDeckDependencies,
) -> SessionSnapshot:
    session_id = await selected_session_id(request, dependencies.session_selector)
    snapshot = await dependencies.store.load(session_id)
    require_current_session(dependencies.app, snapshot.state)
    return snapshot


def project(
    dependencies: RouteDeckDependencies,
    snapshot: SessionSnapshot,
) -> PublicProjection:
    require_current_session(dependencies.app, snapshot.state)
    return dependencies.projector.project(snapshot.state)


def session_creation_fingerprint() -> str:
    return hashlib.sha256(b"routedeck.session-creation.v1").hexdigest()


__all__ = [
    "authenticated_snapshot",
    "GuestCookieSessionSelector",
    "initialize_session",
    "make_session",
    "project",
    "resolve_dependencies",
    "selected_session_id",
    "session_creation_fingerprint",
    "validated_body",
]
