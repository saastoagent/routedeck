from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from medusa_agent.composition import compile_medusa_app_spec
from routedeck_core.contracts.session import LocationParameter
from routedeck_core.navigation.routes import (
    PublicRouteKeyValidator,
    RouteResumeCapability,
    RouteSessionContext,
)
from routedeck_core.validation import RouteDeckValidationError


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CatalogBindingValidator:
    """Explicit test double for the catalog binding's public-key validation."""

    allowed: frozenset[str] = frozenset({"t-shirt", "cafe mug", "a+b.(test)"})

    def is_valid(self, key: str, value: str) -> bool:
        return key == "product_handle" and value in self.allowed


def _catalog_validator() -> PublicRouteKeyValidator:
    return CatalogBindingValidator()


def _context(
    *,
    session_id: str = "guest-1",
    node_id: str = "cart.summary",
    expires_at: datetime | None = None,
    registered_handle: str = "opaque-resume-capability",
) -> RouteSessionContext:
    return RouteSessionContext(
        guest_session_id="guest-1",
        public_key_validator=_catalog_validator(),
        resume_capabilities=(
            RouteResumeCapability(
                handle=registered_handle,
                session_id=session_id,
                node_id=node_id,
                expires_at=expires_at or NOW + timedelta(minutes=5),
                route_params=(
                    (
                        LocationParameter(
                            name="confirmation_handle",
                            value="order-result",
                        ),
                    )
                    if node_id == "orders.confirmation"
                    else ()
                ),
            ),
        ),
        now=NOW,
    )


def test_routes_encode_and_decode_by_declared_segments() -> None:
    routes = compile_medusa_app_spec().routes

    assert (
        routes.encode("catalog.product", {"product_handle": "cafe mug"})
        == "/products/cafe%20mug"
    )
    decoded = routes.decode("/products/cafe%20mug", _context())
    assert decoded.node_id == "catalog.product"
    assert decoded.params == {"product_handle": "cafe mug"}
    with pytest.raises(TypeError):
        decoded.params["product_handle"] = "substituted"

    regex_like = routes.encode("catalog.product", {"product_handle": "a+b.(test)"})
    assert routes.decode(regex_like, _context()).params == {
        "product_handle": "a+b.(test)"
    }


@pytest.mark.parametrize(
    ("node_id", "params"),
    (
        ("catalog.product", {}),
        ("catalog.product", {"product_handle": "t-shirt", "extra": "no"}),
        ("catalog.browse", {"unexpected": "no"}),
    ),
)
def test_encode_rejects_missing_or_extra_parameters(
    node_id: str,
    params: dict[str, str],
) -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_medusa_app_spec().routes.encode(node_id, params)


@pytest.mark.parametrize(
    "path",
    (
        "/orders/confirmation",
        "/products/t-shirt/extra",
        "/products/a%2Fb",
        "/products/%ZZ",
        "/unknown",
        "/checkout/payment/extra",
    ),
)
def test_decode_rejects_extra_or_unknown_segments(path: str) -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_medusa_app_spec().routes.decode(path, _context())


def test_product_handle_must_be_in_the_caller_supplied_public_binding() -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_medusa_app_spec().routes.decode("/products/unknown", _context())


def test_structural_match_exposes_unseen_shareable_route_arguments() -> None:
    match = compile_medusa_app_spec().routes.match("/products/unseen-handle")

    assert match.node_id == "catalog.product"
    assert match.params == {"product_handle": "unseen-handle"}
    assert match.resume_handle is None


def test_structural_match_exposes_an_unvalidated_session_resume_handle() -> None:
    routes = compile_medusa_app_spec().routes

    match = routes.match("/cart?resume_handle=unregistered%2Bhandle")

    assert match.node_id == "cart.summary"
    assert match.params == {}
    assert match.resume_handle == "unregistered+handle"
    with pytest.raises(RouteDeckValidationError):
        routes.decode("/cart?resume_handle=unregistered%2Bhandle", None)


@pytest.mark.parametrize(
    "path",
    (
        "/products/unseen?unexpected=value",
        "/cart",
        "/cart?resume_handle=one&resume_handle=two",
    ),
)
def test_structural_match_rejects_malformed_route_queries(path: str) -> None:
    with pytest.raises(RouteDeckValidationError):
        compile_medusa_app_spec().routes.match(path)


def test_route_matching_normalizes_repeated_and_trailing_slashes() -> None:
    decoded = compile_medusa_app_spec().routes.decode("/products//t-shirt/", _context())

    assert decoded.node_id == "catalog.product"
    assert decoded.params == {"product_handle": "t-shirt"}


@pytest.mark.parametrize(
    "node_id",
    (
        "cart.summary",
        "checkout.contact",
        "checkout.delivery",
        "checkout.payment",
        "checkout.review",
        "orders.confirmation",
    ),
)
def test_private_routes_require_a_matching_session_bound_capability(
    node_id: str,
) -> None:
    routes = compile_medusa_app_spec().routes
    path = routes.encode(
        node_id,
        {
            **(
                {"confirmation_handle": "order-result"}
                if node_id == "orders.confirmation"
                else {}
            ),
            "resume_handle": "opaque-resume-capability",
        },
    )

    with pytest.raises(RouteDeckValidationError):
        routes.decode(path, None)
    with pytest.raises(RouteDeckValidationError):
        routes.decode(path.split("?", 1)[0], _context(node_id=node_id))
    with pytest.raises(RouteDeckValidationError):
        routes.decode(
            path.replace("opaque-resume-capability", "wrong-handle"),
            _context(node_id=node_id),
        )
    with pytest.raises(RouteDeckValidationError):
        routes.decode(path, _context(session_id="different", node_id=node_id))
    with pytest.raises(RouteDeckValidationError):
        routes.decode(path, _context(node_id="catalog.browse"))
    with pytest.raises(RouteDeckValidationError):
        routes.decode(
            path,
            _context(node_id=node_id, expires_at=NOW - timedelta(seconds=1)),
        )

    decoded = routes.decode(path, _context(node_id=node_id))
    assert decoded.node_id == node_id


def test_decoding_is_pure_and_never_creates_replacement_state() -> None:
    routes = compile_medusa_app_spec().routes
    context = _context(node_id="checkout.review")
    before = (
        context.guest_session_id,
        context.resume_capabilities,
        context.now,
    )

    routes.decode("/checkout/review?resume_handle=opaque-resume-capability", context)

    assert (
        context.guest_session_id,
        context.resume_capabilities,
        context.now,
    ) == before
