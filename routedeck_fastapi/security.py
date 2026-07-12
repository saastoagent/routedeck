from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

from starlette.requests import Request


class RouteDeckMutationRejected(RuntimeError):
    """Raised when browser request provenance is not authorized for mutation."""


@runtime_checkable
class RouteDeckMutationPolicy(Protocol):
    def authorize(self, request: Request) -> None: ...


@dataclass(frozen=True)
class SameOriginMutationPolicy:
    """Allow same-origin browsers, explicit trusted origins, and non-browser clients."""

    trusted_origins: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        normalized = frozenset(
            _normalized_origin(origin) for origin in self.trusted_origins
        )
        if normalized != self.trusted_origins:
            raise ValueError("trusted mutation origins must use canonical origins")

    def authorize(self, request: Request) -> None:
        origin = request.headers.get("origin")
        if origin is not None:
            allowed = self.trusted_origins | {_request_origin(request)}
            if origin not in allowed:
                raise RouteDeckMutationRejected(
                    "The mutation request origin is not authorized."
                )
            return

        fetch_site = request.headers.get("sec-fetch-site")
        if fetch_site is not None and fetch_site.lower() not in {
            "none",
            "same-origin",
        }:
            raise RouteDeckMutationRejected(
                "The mutation request site is not authorized."
            )


def _request_origin(request: Request) -> str:
    return f"{request.url.scheme.lower()}://{request.url.netloc.lower()}"


def _normalized_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("trusted mutation origins must be absolute HTTP origins")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


__all__ = [
    "RouteDeckMutationPolicy",
    "RouteDeckMutationRejected",
    "SameOriginMutationPolicy",
]
