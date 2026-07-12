from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from medusa_agent.composition import compile_medusa_app_spec
from routedeck_core.navigation.deep_links import DeepLinkEngine, SessionRequired
from routedeck_core.navigation.routes import (
    CompiledRoutes,
    RouteCapabilityMismatch,
    RouteResumeCapability,
    RouteSessionContext,
    RouteSessionRequired,
)
from routedeck_core.validation import RouteDeckValidationError


NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


def _capability(handle: str = "resume-1") -> RouteResumeCapability:
    return RouteResumeCapability(
        handle=handle,
        session_id="session-1",
        node_id="cart.summary",
        expires_at=NOW + timedelta(minutes=5),
    )


def test_route_session_context_rejects_naive_time_and_duplicate_capabilities() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        RouteSessionContext(now=datetime(2026, 7, 12, 12, 0))

    capability = _capability()
    with pytest.raises(ValidationError, match="handles must be unique"):
        RouteSessionContext(
            now=NOW,
            resume_capabilities=(capability, capability),
        )


def test_session_bound_link_encoding_requires_session_and_clock() -> None:
    with pytest.raises(SessionRequired, match="authenticated session"):
        DeepLinkEngine(compile_medusa_app_spec()).encode(
            "cart.summary",
            {"resume_handle": "resume-1"},
        )


def test_route_lookup_helpers_reject_unknown_nodes_and_wrong_binding_shapes() -> None:
    routes = compile_medusa_app_spec().routes

    with pytest.raises(RouteDeckValidationError, match="Unknown route node"):
        routes.encode("missing.node", {})
    with pytest.raises(RouteDeckValidationError, match="Unknown route node"):
        routes.validate_path_bindings("missing.node", {})
    with pytest.raises(RouteDeckValidationError, match="requires path parameters"):
        routes.validate_path_bindings("catalog.product", {})
    with pytest.raises(RouteDeckValidationError, match="Unknown route node"):
        routes.deep_link_policy("missing.node")
    with pytest.raises(RouteDeckValidationError, match="Unknown route node"):
        routes.validate_public_bindings("missing.node", {}, None)
    with pytest.raises(RouteDeckValidationError, match="does not declare shareable"):
        routes.validate_public_bindings("cart.summary", {}, None)
    with pytest.raises(RouteDeckValidationError, match="requires parameters"):
        routes.validate_public_bindings("catalog.product", {}, None)


def test_route_encoding_rejects_empty_resume_and_unsafe_path_segments() -> None:
    routes = compile_medusa_app_spec().routes

    with pytest.raises(RouteDeckValidationError, match="resume_handle"):
        routes.encode("cart.summary", {"resume_handle": ""})
    with pytest.raises(RouteDeckValidationError, match="must be non-empty"):
        routes.encode("catalog.product", {"product_handle": ""})
    with pytest.raises(RouteDeckValidationError, match="contains a separator"):
        routes.encode("catalog.product", {"product_handle": "private/id"})


@pytest.mark.parametrize(
    "path, expected_error",
    (
        ("https://example.test/products", RouteDeckValidationError),
        ("/products#private", RouteDeckValidationError),
        ("/cart?resume_handle", RouteCapabilityMismatch),
        ("/products/%FF", RouteDeckValidationError),
    ),
)
def test_route_parser_rejects_nonlocal_malformed_or_non_utf8_paths(
    path: str,
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error):
        compile_medusa_app_spec().routes.match(path)


def test_session_bound_decode_requires_authenticated_guest_identity() -> None:
    context = RouteSessionContext(
        guest_session_id=None,
        now=NOW,
        resume_capabilities=(_capability(),),
    )

    with pytest.raises(RouteSessionRequired, match="authenticated guest"):
        compile_medusa_app_spec().routes.decode(
            "/cart?resume_handle=resume-1",
            context,
        )


@pytest.mark.parametrize(
    "template",
    (
        "products",
        "/products?private=true",
        "/products/",
        "/products/{handle}/{handle}",
        "/products/prefix-{handle}",
    ),
)
def test_route_compilation_rejects_ambiguous_or_noncanonical_templates(
    template: str,
) -> None:
    node = compile_medusa_app_spec().spec.nodes[0]
    forged = node.model_copy(
        update={"route": node.route.model_copy(update={"template": template})}
    )

    with pytest.raises(RouteDeckValidationError):
        CompiledRoutes.from_nodes((forged,))
