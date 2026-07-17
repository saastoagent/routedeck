from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from string import hexdigits
from types import MappingProxyType
from typing import Protocol, runtime_checkable
from urllib.parse import quote, unquote_to_bytes, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..contracts.application import Node
from ..contracts.navigation import DeepLinkPolicy
from ..contracts.session import LocationParameter, ResumeCapabilityBinding
from ..validation import RouteDeckValidationError


@runtime_checkable
class PublicRouteKeyValidator(Protocol):
    def is_valid(self, key: str, value: str) -> bool: ...


class RouteSessionRequired(RouteDeckValidationError):
    """Raised when a session-bound route has no authenticated session."""


class RouteCapabilityMismatch(RouteDeckValidationError):
    """Raised when a session-bound route capability is missing or invalid."""


class _FrozenContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )


class RouteSessionContext(_FrozenContract):
    guest_session_id: str | None = Field(default=None, min_length=1)
    public_key_validator: PublicRouteKeyValidator | None = None
    resume_capabilities: tuple[ResumeCapabilityBinding, ...] = ()
    now: datetime

    @model_validator(mode="after")
    def _requires_aware_clock(self) -> RouteSessionContext:
        if self.now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        handles = tuple(capability.handle for capability in self.resume_capabilities)
        if len(handles) != len(set(handles)):
            raise ValueError("resume capability handles must be unique")
        return self

    def resume_capability(self, handle: str) -> ResumeCapabilityBinding | None:
        return next(
            (
                capability
                for capability in self.resume_capabilities
                if capability.handle == handle
            ),
            None,
        )


class DecodedRoute(_FrozenContract):
    node_id: str
    route_params: tuple[LocationParameter, ...] = ()

    @property
    def route_bindings(self) -> Mapping[str, str]:
        return MappingProxyType(
            {parameter.name: parameter.value for parameter in self.route_params}
        )


class StructuralRouteMatch(_FrozenContract):
    """One structurally valid route before product or capability authorization."""

    node_id: str
    route_params: tuple[LocationParameter, ...] = ()
    resume_handle: str | None = None

    @property
    def route_bindings(self) -> Mapping[str, str]:
        return MappingProxyType(
            {parameter.name: parameter.value for parameter in self.route_params}
        )


@dataclass(frozen=True)
class _RouteSegment:
    literal: str | None = None
    parameter: str | None = None


@dataclass(frozen=True)
class _CompiledRoute:
    node_id: str
    template: str
    deep_link_policy: DeepLinkPolicy
    segments: tuple[_RouteSegment, ...]

    @property
    def parameter_names(self) -> tuple[str, ...]:
        return tuple(
            segment.parameter
            for segment in self.segments
            if segment.parameter is not None
        )


class CompiledRoutes:
    def __init__(self, routes: tuple[_CompiledRoute, ...]) -> None:
        self._routes = routes
        self._by_node = {route.node_id: route for route in routes}

    @classmethod
    def from_nodes(cls, nodes: tuple[Node, ...]) -> CompiledRoutes:
        routes: list[_CompiledRoute] = []
        for node in nodes:
            route = _compile_route(
                node_id=node.id,
                template=node.route.template,
                deep_link_policy=node.route.deep_link_policy,
            )
            for previous in routes:
                if _routes_overlap(previous, route):
                    raise RouteDeckValidationError(
                        f"Route {node.id!r} overlaps route {previous.node_id!r}"
                    )
            routes.append(route)
        return cls(tuple(routes))

    def encode(self, node_id: str, params: Mapping[str, str]) -> str:
        route = self._by_node.get(node_id)
        if route is None:
            raise RouteDeckValidationError(f"Unknown route node: {node_id}")

        expected = set(route.parameter_names)
        if route.deep_link_policy is DeepLinkPolicy.SESSION_BOUND:
            expected.add("resume_handle")
        actual = set(params)
        if actual != expected:
            raise RouteDeckValidationError(
                f"Route {node_id!r} requires parameters {sorted(expected)!r}; "
                f"received {sorted(actual)!r}"
            )

        path_bindings = {name: params[name] for name in route.parameter_names}
        self.validate_path_bindings(node_id, path_bindings)

        encoded_segments: list[str] = []
        for segment in route.segments:
            if segment.literal is not None:
                encoded_segments.append(segment.literal)
                continue
            parameter = segment.parameter
            if parameter is None:
                raise RouteDeckValidationError("Route segment has no declaration")
            encoded_segments.append(_encode_segment(parameter, params[parameter]))

        path = "/" + "/".join(encoded_segments)
        if route.deep_link_policy is DeepLinkPolicy.SESSION_BOUND:
            handle = params["resume_handle"]
            if not isinstance(handle, str) or not handle:
                raise RouteDeckValidationError(
                    "resume_handle must be a non-empty string"
                )
            path += f"?resume_handle={quote(handle, safe='')}"
        return path

    def validate_path_bindings(
        self,
        node_id: str,
        params: Mapping[str, str],
    ) -> None:
        """Validate exact canonical path bindings without deep-link credentials."""

        route = self._by_node.get(node_id)
        if route is None:
            raise RouteDeckValidationError(f"Unknown route node: {node_id}")
        expected = set(route.parameter_names)
        actual = set(params)
        if actual != expected:
            raise RouteDeckValidationError(
                f"Route {node_id!r} requires path parameters {sorted(expected)!r}; "
                f"received {sorted(actual)!r}"
            )
        for name in route.parameter_names:
            _encode_segment(name, params[name])

    def path_parameter_names(self, node_id: str) -> tuple[str, ...]:
        """Return the declared path parameters for one compiled node route."""

        route = self._by_node.get(node_id)
        if route is None:
            raise RouteDeckValidationError(f"Unknown route node: {node_id}")
        return route.parameter_names

    def deep_link_policy(self, node_id: str) -> DeepLinkPolicy:
        """Return the compiled deep-link policy for one node."""

        route = self._by_node.get(node_id)
        if route is None:
            raise RouteDeckValidationError(f"Unknown route node: {node_id}")
        return route.deep_link_policy

    def validate_public_bindings(
        self,
        node_id: str,
        params: Mapping[str, str],
        validator: PublicRouteKeyValidator | None,
    ) -> None:
        """Validate declared shareable path keys through an injected authority."""

        route = self._by_node.get(node_id)
        if route is None:
            raise RouteDeckValidationError(f"Unknown route node: {node_id}")
        if route.deep_link_policy is not DeepLinkPolicy.SHAREABLE:
            raise RouteDeckValidationError(
                f"Node {node_id!r} does not declare shareable route bindings"
            )
        expected = set(route.parameter_names)
        actual = set(params)
        if actual != expected:
            raise RouteDeckValidationError(
                f"Route {node_id!r} requires parameters {sorted(expected)!r}; "
                f"received {sorted(actual)!r}"
            )
        if not route.parameter_names:
            return
        if validator is None:
            raise RouteDeckValidationError(
                "Public route parameters require a caller-supplied validator"
            )
        for key in route.parameter_names:
            value = params[key]
            _encode_segment(key, value)
            if not validator.is_valid(key, value):
                raise RouteDeckValidationError(
                    f"Public route binding is not valid for {key!r}"
                )

    def decode(
        self,
        path: str,
        session_context: RouteSessionContext | None,
    ) -> DecodedRoute:
        matched = self.match(path)
        route = self._by_node[matched.node_id]
        params = dict(matched.route_bindings)

        if route.deep_link_policy is DeepLinkPolicy.SHAREABLE:
            validator = (
                session_context.public_key_validator
                if session_context is not None
                else None
            )
            self.validate_public_bindings(route.node_id, params, validator)
        else:
            self._validate_resume_capability(
                route=route,
                route_params=matched.route_params,
                resume_handle=matched.resume_handle,
                session_context=session_context,
            )
        return DecodedRoute(
            node_id=matched.node_id,
            route_params=matched.route_params,
        )

    def match(self, path: str) -> StructuralRouteMatch:
        """Parse one declared local route without semantic authorization."""

        split = urlsplit(path)
        if split.scheme or split.netloc or split.fragment:
            raise RouteDeckValidationError(
                "Route must be a local path without a fragment"
            )

        raw_segments = tuple(segment for segment in split.path.split("/") if segment)
        decoded_segments = tuple(_decode_segment(segment) for segment in raw_segments)
        matches: list[tuple[_CompiledRoute, dict[str, str]]] = []
        for route in self._routes:
            if len(route.segments) != len(decoded_segments):
                continue
            params: dict[str, str] = {}
            matched = True
            for declaration, value in zip(
                route.segments, decoded_segments, strict=True
            ):
                if declaration.literal is not None:
                    if value != declaration.literal:
                        matched = False
                        break
                elif declaration.parameter is not None:
                    if not value:
                        matched = False
                        break
                    params[declaration.parameter] = value
            if matched:
                matches.append((route, params))

        if len(matches) != 1:
            raise RouteDeckValidationError(
                f"Path does not identify one declared route: {path}"
            )
        route, params = matches[0]
        route_params = tuple(
            LocationParameter(name=name, value=params[name])
            for name in route.parameter_names
        )

        if route.deep_link_policy is DeepLinkPolicy.SHAREABLE:
            if split.query:
                raise RouteDeckValidationError(
                    "Shareable routes do not accept query bindings"
                )
            resume_handle = None
        else:
            resume_handle = self._decode_resume_handle(split.query)
        return StructuralRouteMatch(
            node_id=route.node_id,
            route_params=route_params,
            resume_handle=resume_handle,
        )

    @staticmethod
    def _decode_resume_handle(raw_query: str) -> str:
        query_parts = raw_query.split("&") if raw_query else []
        if len(query_parts) != 1:
            raise RouteCapabilityMismatch(
                "Session-bound route requires exactly one resume_handle"
            )
        raw_key, separator, raw_value = query_parts[0].partition("=")
        if not separator:
            raise RouteCapabilityMismatch("resume_handle query binding is malformed")
        key = _decode_segment(raw_key)
        handle = _decode_segment(raw_value)
        if key != "resume_handle" or not handle:
            raise RouteCapabilityMismatch(
                "Session-bound route requires exactly one resume_handle"
            )
        return handle

    @staticmethod
    def _validate_resume_capability(
        *,
        route: _CompiledRoute,
        route_params: tuple[LocationParameter, ...],
        resume_handle: str | None,
        session_context: RouteSessionContext | None,
    ) -> None:
        if session_context is None:
            raise RouteSessionRequired(
                "Session-bound route requires authenticated guest session context"
            )
        if session_context.guest_session_id is None:
            raise RouteSessionRequired(
                "Session-bound route requires authenticated guest session context"
            )
        if resume_handle is None:
            raise RouteCapabilityMismatch(
                "Session-bound route requires exactly one resume_handle"
            )
        handle = resume_handle
        capability = session_context.resume_capability(handle)
        if capability is None or capability.handle != handle:
            raise RouteCapabilityMismatch("Resume capability is unknown")
        if capability.session_id != session_context.guest_session_id:
            raise RouteCapabilityMismatch(
                "Resume capability belongs to another session"
            )
        if capability.node_id != route.node_id:
            raise RouteCapabilityMismatch("Resume capability belongs to another node")
        if capability.expires_at <= session_context.now:
            raise RouteCapabilityMismatch("Resume capability has expired")
        if capability.route_params != route_params:
            raise RouteCapabilityMismatch(
                "Resume capability belongs to different route parameters"
            )


def _compile_route(
    *,
    node_id: str,
    template: str,
    deep_link_policy: DeepLinkPolicy,
) -> _CompiledRoute:
    if not template.startswith("/") or "?" in template or "#" in template:
        raise RouteDeckValidationError(f"Invalid route template: {template!r}")
    if template != "/" and (template.endswith("/") or "//" in template):
        raise RouteDeckValidationError(
            f"Route template is not normalized: {template!r}"
        )

    raw_segments = tuple(segment for segment in template.split("/") if segment)
    segments: list[_RouteSegment] = []
    parameters: set[str] = set()
    for value in raw_segments:
        if value.startswith("{") and value.endswith("}"):
            parameter = value[1:-1]
            if not parameter.isidentifier() or parameter in parameters:
                raise RouteDeckValidationError(
                    f"Invalid route parameter in template: {template!r}"
                )
            parameters.add(parameter)
            segments.append(_RouteSegment(parameter=parameter))
        else:
            if "{" in value or "}" in value:
                raise RouteDeckValidationError(
                    f"Route parameters must occupy a complete segment: {template!r}"
                )
            segments.append(_RouteSegment(literal=value))
    return _CompiledRoute(
        node_id=node_id,
        template=template,
        deep_link_policy=deep_link_policy,
        segments=tuple(segments),
    )


def _routes_overlap(left: _CompiledRoute, right: _CompiledRoute) -> bool:
    if len(left.segments) != len(right.segments):
        return False
    for left_segment, right_segment in zip(left.segments, right.segments, strict=True):
        if (
            left_segment.literal is not None
            and right_segment.literal is not None
            and left_segment.literal != right_segment.literal
        ):
            return False
    return True


def _encode_segment(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise RouteDeckValidationError(f"Route parameter {name!r} must be non-empty")
    if "/" in value or "\\" in value:
        raise RouteDeckValidationError(f"Route parameter {name!r} contains a separator")
    return quote(value, safe="")


def _decode_segment(value: str) -> str:
    index = 0
    while index < len(value):
        if value[index] == "%":
            if (
                index + 2 >= len(value)
                or value[index + 1] not in hexdigits
                or value[index + 2] not in hexdigits
            ):
                raise RouteDeckValidationError(
                    "Route contains malformed percent encoding"
                )
            index += 3
            continue
        index += 1
    try:
        decoded = unquote_to_bytes(value).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RouteDeckValidationError("Route contains invalid UTF-8 encoding") from exc
    if "/" in decoded or "\\" in decoded:
        raise RouteDeckValidationError("Decoded route segment contains a separator")
    return decoded


__all__ = [
    "CompiledRoutes",
    "DecodedRoute",
    "PublicRouteKeyValidator",
    "RouteCapabilityMismatch",
    "RouteSessionRequired",
    "RouteSessionContext",
    "StructuralRouteMatch",
]
