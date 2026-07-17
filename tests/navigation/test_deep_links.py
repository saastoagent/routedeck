from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from medusa_agent.composition import compile_medusa_app
from routedeck_core.contracts.session import LocationParameter, ResumeCapabilityBinding
from routedeck_core.navigation.deep_links import DeepLinkEngine
from routedeck_core.navigation.routes import (
    PublicRouteKeyValidator,
    RouteCapabilityMismatch,
    RouteSessionRequired,
)
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import session_factory


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CatalogValidator:
    def is_valid(self, key: str, value: str) -> bool:
        return key == "product_handle" and value == "t-shirt"


def _validator() -> PublicRouteKeyValidator:
    return CatalogValidator()


def _capability(
    *,
    handle: str = "opaque-capability",
    session_id: str = "session-1",
    node_id: str = "cart.summary",
    expires_at: datetime | None = None,
    route_params: tuple[LocationParameter, ...] = (),
) -> ResumeCapabilityBinding:
    return ResumeCapabilityBinding(
        handle=handle,
        session_id=session_id,
        node_id=node_id,
        expires_at=expires_at or NOW + timedelta(minutes=5),
        route_params=route_params,
    )


def test_public_and_session_bound_deep_links_are_distinct() -> None:
    app = compile_medusa_app()
    engine = DeepLinkEngine(app)
    public = engine.open(
        "/products/t-shirt",
        session=None,
        public_key_validator=_validator(),
        now=NOW,
    )
    assert public.node_id == "catalog.product"

    with pytest.raises(RouteSessionRequired):
        engine.open(
            "/cart?resume_handle=opaque-capability",
            session=None,
            now=NOW,
        )
    valid_session = session_factory(app=app, session_id="session-1")
    cross_session_capability = _capability(session_id="other-session")
    malformed_session = valid_session.model_copy(
        update={
            "private_state": valid_session.private_state.model_copy(
                update={"resume_capabilities": (cross_session_capability,)}
            )
        }
    )
    with pytest.raises(RouteCapabilityMismatch):
        engine.open(
            "/cart?resume_handle=opaque-capability",
            session=malformed_session,
            now=NOW,
        )


@pytest.mark.parametrize(
    "path",
    (
        "/cart?resume_handle=opaque-capability",
        "/checkout/review?resume_handle=opaque-capability",
        "/orders/confirmation/confirmation?resume_handle=opaque-capability",
    ),
)
def test_representative_session_bound_routes_require_a_session(path: str) -> None:
    with pytest.raises(RouteSessionRequired):
        DeepLinkEngine(compile_medusa_app()).open(
            path,
            session=None,
            now=NOW,
        )


def test_valid_cart_and_confirmation_capabilities_open_bound_routes() -> None:
    app = compile_medusa_app()
    cart_capability = _capability()
    confirmation_capability = _capability(
        handle="confirmation-capability",
        node_id="orders.confirmation",
        route_params=(
            LocationParameter(name="confirmation_handle", value="confirmation"),
        ),
    )
    session = session_factory(
        app=app,
        session_id="session-1",
        resume_capabilities=(cart_capability, confirmation_capability),
    )
    engine = DeepLinkEngine(app)

    cart = engine.open(
        "/cart?resume_handle=opaque-capability",
        session=session,
        now=NOW,
    )
    confirmation = engine.open(
        "/orders/confirmation/confirmation?resume_handle=confirmation-capability",
        session=session,
        now=NOW,
    )

    assert cart.node_id == "cart.summary"
    assert confirmation.node_id == "orders.confirmation"
    assert confirmation.route_bindings == {"confirmation_handle": "confirmation"}


def test_session_capability_rejects_path_parameter_substitution() -> None:
    app = compile_medusa_app()
    capability = _capability(
        handle="confirmation-capability",
        node_id="orders.confirmation",
        route_params=(
            LocationParameter(name="confirmation_handle", value="confirmation"),
        ),
    )
    session = session_factory(app=app, resume_capabilities=(capability,))
    engine = DeepLinkEngine(app)

    with pytest.raises(RouteCapabilityMismatch):
        engine.open(
            "/orders/substituted/confirmation?resume_handle=confirmation-capability",
            session=session,
            now=NOW,
        )
    with pytest.raises(RouteCapabilityMismatch):
        engine.encode(
            "orders.confirmation",
            {
                "confirmation_handle": "substituted",
                "resume_handle": "confirmation-capability",
            },
            session=session,
            now=NOW,
        )


def test_shareable_link_generation_requires_an_injected_public_key_validator() -> None:
    engine = DeepLinkEngine(compile_medusa_app())

    with pytest.raises(RouteDeckValidationError):
        engine.encode("catalog.product", {"product_handle": "t-shirt"})
    with pytest.raises(RouteDeckValidationError):
        engine.encode(
            "catalog.product",
            {"product_handle": "cart_private_123"},
            public_key_validator=_validator(),
        )

    assert (
        engine.encode(
            "catalog.product",
            {"product_handle": "t-shirt"},
            public_key_validator=_validator(),
        )
        == "/products/t-shirt"
    )


@pytest.mark.parametrize(
    ("capabilities", "path"),
    (
        (
            (_capability(expires_at=NOW - timedelta(seconds=1)),),
            "/cart?resume_handle=opaque-capability",
        ),
        (
            (_capability(node_id="checkout.review"),),
            "/cart?resume_handle=opaque-capability",
        ),
        (
            (_capability(handle="different-capability"),),
            "/cart?resume_handle=opaque-capability",
        ),
    ),
)
def test_expired_wrong_node_and_unknown_capabilities_fail_explicitly(
    capabilities: tuple[ResumeCapabilityBinding, ...],
    path: str,
) -> None:
    app = compile_medusa_app()
    with pytest.raises(RouteCapabilityMismatch):
        DeepLinkEngine(app).open(
            path,
            session=session_factory(app=app, resume_capabilities=capabilities),
            now=NOW,
        )


def test_invalid_public_binding_and_missing_resume_handle_fail_explicitly() -> None:
    app = compile_medusa_app()
    engine = DeepLinkEngine(app)

    with pytest.raises(RouteDeckValidationError):
        engine.open(
            "/products/not-allowlisted",
            session=None,
            public_key_validator=_validator(),
            now=NOW,
        )
    with pytest.raises(RouteCapabilityMismatch):
        engine.open(
            "/cart",
            session=session_factory(
                app=app,
                resume_capabilities=(_capability(),),
            ),
            now=NOW,
        )


def test_generated_session_link_contains_no_session_or_private_id() -> None:
    app = compile_medusa_app()
    engine = DeepLinkEngine(app)
    session = session_factory(app=app, resume_capabilities=(_capability(),))

    link = engine.encode(
        "cart.summary",
        {"resume_handle": "opaque-capability"},
        session=session,
        now=NOW,
    )

    assert link == "/cart?resume_handle=opaque-capability"
    assert "session-1" not in link
    assert "cart_" not in link

    confirmation = engine.encode(
        "orders.confirmation",
        {
            "confirmation_handle": "confirmation",
            "resume_handle": "confirmation-capability",
        },
        session=session_factory(
            app=app,
            resume_capabilities=(
                _capability(
                    handle="confirmation-capability",
                    node_id="orders.confirmation",
                    route_params=(
                        LocationParameter(
                            name="confirmation_handle",
                            value="confirmation",
                        ),
                    ),
                ),
            ),
        ),
        now=NOW,
    )
    assert confirmation == (
        "/orders/confirmation/confirmation?resume_handle=confirmation-capability"
    )

    with pytest.raises(RouteDeckValidationError):
        engine.encode(
            "cart.summary",
            {
                "resume_handle": "opaque-capability",
                "cart_id": "cart_private_123",
            },
            session=session,
            now=NOW,
        )
    with pytest.raises(RouteCapabilityMismatch):
        engine.encode(
            "cart.summary",
            {"resume_handle": "cart_private_123"},
            session=session,
            now=NOW,
        )


def test_session_bound_links_reject_an_incompatible_navgraph_session() -> None:
    app = compile_medusa_app()
    stale = session_factory(resume_capabilities=(_capability(),))

    with pytest.raises(RouteDeckValidationError, match="session_upgrade_required"):
        DeepLinkEngine(app).open(
            "/cart?resume_handle=opaque-capability",
            session=stale,
            now=NOW,
        )
