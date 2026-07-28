from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from routedeck_fastapi import (
    GuestCookieSessionSelector,
    GuestCookieSettings,
    RouteDeckSessionSelector,
)
from routedeck_fastapi.contracts import RouteDeckHttpProblem
from routedeck_fastapi.session_http import selected_session_id


def request_with_headers(*headers: tuple[bytes, bytes]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/routedeck/session",
            "headers": list(headers),
        }
    )


def test_guest_cookie_policy_must_be_explicit() -> None:
    with pytest.raises(TypeError):
        GuestCookieSettings()  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_guest_selector_reads_and_attaches_the_configured_cookie() -> None:
    selector = GuestCookieSessionSelector(
        GuestCookieSettings(name="route_session", secure=False, path="/shop")
    )
    request = request_with_headers((b"cookie", b"route_session=session-internal-1"))

    assert await selected_session_id(request, selector) == "session-internal-1"

    response = JSONResponse({"ok": True})
    await selector.attach_created_session(
        request,
        response,
        "session-internal-2",
    )
    cookie = response.headers["set-cookie"]
    assert "route_session=session-internal-2" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/shop" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie


@dataclass
class PrincipalHandleSelector:
    authorized: dict[tuple[str, str], str]
    attached: list[str] = field(default_factory=list)

    async def selected_session_id(self, request: Request) -> str:
        principal = request.headers.get("x-principal", "")
        handle = request.headers.get("x-session-handle", "")
        try:
            return self.authorized[(principal, handle)]
        except KeyError as error:
            raise RouteDeckHttpProblem(
                404,
                "session_not_found",
                "The selected session is unavailable.",
            ) from error

    async def attach_created_session(
        self,
        request: Request,
        response: JSONResponse,
        session_id: str,
    ) -> None:
        del request, response
        self.attached.append(session_id)


@pytest.mark.asyncio
async def test_host_selector_can_isolate_users_and_multiple_sessions() -> None:
    selector = PrincipalHandleSelector(
        authorized={
            ("user-a", "work"): "internal-a-work",
            ("user-a", "personal"): "internal-a-personal",
            ("user-b", "work"): "internal-b-work",
        }
    )
    assert isinstance(selector, RouteDeckSessionSelector)

    user_a_work = request_with_headers(
        (b"x-principal", b"user-a"),
        (b"x-session-handle", b"work"),
    )
    user_a_personal = request_with_headers(
        (b"x-principal", b"user-a"),
        (b"x-session-handle", b"personal"),
    )
    user_b_work = request_with_headers(
        (b"x-principal", b"user-b"),
        (b"x-session-handle", b"work"),
    )

    assert await selected_session_id(user_a_work, selector) == "internal-a-work"
    assert (
        await selected_session_id(user_a_personal, selector)
        == "internal-a-personal"
    )
    assert await selected_session_id(user_b_work, selector) == "internal-b-work"

    cross_user = request_with_headers(
        (b"x-principal", b"user-b"),
        (b"x-session-handle", b"personal"),
    )
    with pytest.raises(RouteDeckHttpProblem) as rejected:
        await selected_session_id(cross_user, selector)
    assert rejected.value.code == "session_not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", ("", "x" * 513))
async def test_selector_output_must_be_a_bounded_non_empty_session_id(
    selected: str,
) -> None:
    selector = PrincipalHandleSelector(authorized={("user", "handle"): selected})
    request = request_with_headers(
        (b"x-principal", b"user"),
        (b"x-session-handle", b"handle"),
    )

    with pytest.raises(RouteDeckHttpProblem) as invalid:
        await selected_session_id(request, selector)
    assert invalid.value.code == "session_selection_invalid"
