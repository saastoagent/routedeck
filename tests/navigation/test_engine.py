from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest

from medusa_agent.composition import compile_medusa_app_spec
from routedeck_core.contracts.navigation import NodeRef
from routedeck_core.contracts.session import Location, LocationParameter
from routedeck_core.navigation.engine import NavigationEngine
from routedeck_core.navigation.deep_links import CapabilityMismatch
from routedeck_core.navigation.routes import RouteResumeCapability
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import session_factory


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CatalogValidator:
    def is_valid(self, key: str, value: str) -> bool:
        return key == "product_handle" and value == "t-shirt"


def test_navigation_uses_compiled_nodes_and_immutable_history() -> None:
    app = compile_medusa_app_spec()
    initial = session_factory(app=app, node_id="buyer.home")
    engine = NavigationEngine(app)

    browsed = engine.open(initial, node_id="catalog.browse")
    product = engine.open(
        browsed,
        node_id="catalog.product",
        route_params={"product_handle": "t-shirt"},
        public_key_validator=CatalogValidator(),
    )
    backed = engine.back(
        product,
        public_key_validator=CatalogValidator(),
    )

    assert initial.current.node_id == "buyer.home"
    assert product.current.node_id == "catalog.product"
    assert tuple(location.node_id for location in product.back_stack) == (
        "buyer.home",
        "catalog.browse",
    )
    assert {
        (parameter.name, parameter.value) for parameter in product.current.route_params
    } == {("product_handle", "t-shirt")}
    assert backed.current.node_id == "catalog.browse"
    assert backed.forward_stack[-1].node_id == "catalog.product"
    assert browsed.session_version == initial.session_version + 1
    assert browsed.projection_version == initial.projection_version + 1
    assert product.session_version == browsed.session_version + 1
    assert product.projection_version == browsed.projection_version + 1
    assert backed.session_version == product.session_version + 1
    assert backed.projection_version == product.projection_version + 1
    assert backed.event_cursor == initial.event_cursor


def test_forward_cancel_and_new_open_update_history_without_mutating_inputs() -> None:
    app = compile_medusa_app_spec()
    engine = NavigationEngine(app)
    home = session_factory(app=app, node_id="buyer.home")
    browsed = engine.open(home, node_id="catalog.browse")
    product = engine.open(
        browsed,
        node_id="catalog.product",
        route_params={"product_handle": "t-shirt"},
        public_key_validator=CatalogValidator(),
    )
    backed = engine.back(
        product,
        public_key_validator=CatalogValidator(),
    )

    forwarded = engine.forward(
        backed,
        public_key_validator=CatalogValidator(),
    )
    cancelled = engine.cancel(
        forwarded,
        public_key_validator=CatalogValidator(),
    )
    newly_opened = engine.open(backed, node_id="buyer.home")

    assert backed.current.node_id == "catalog.browse"
    assert forwarded.current == product.current
    assert forwarded.forward_stack == ()
    assert cancelled.current.node_id == "catalog.browse"
    assert cancelled.forward_stack[-1] == product.current
    assert newly_opened.current.node_id == "buyer.home"
    assert newly_opened.forward_stack == ()


def test_empty_history_navigation_is_an_identity_preserving_noop() -> None:
    app = compile_medusa_app_spec()
    initial = session_factory(app=app, node_id="buyer.home")
    engine = NavigationEngine(app)

    assert engine.back(initial) is initial
    assert engine.forward(initial) is initial
    assert engine.cancel(initial) is initial


def test_navigation_rejects_unknown_nodes_and_invalid_route_parameters() -> None:
    app = compile_medusa_app_spec()
    initial = session_factory(app=app, node_id="buyer.home")
    engine = NavigationEngine(app)

    with pytest.raises(RouteDeckValidationError):
        engine.open(initial, node_id="missing.node")
    with pytest.raises(RouteDeckValidationError):
        engine.open(initial, node_id="catalog.product")
    with pytest.raises(RouteDeckValidationError):
        engine.open(
            initial,
            node_id="buyer.home",
            route_params={"private_id": "cart_private_123"},
        )


def test_navigation_validates_public_path_bindings_before_state_changes() -> None:
    app = compile_medusa_app_spec()
    initial = session_factory(app=app, node_id="catalog.browse")
    engine = NavigationEngine(app)

    with pytest.raises(RouteDeckValidationError):
        engine.open(
            initial,
            node_id="catalog.product",
            route_params={"product_handle": "t-shirt"},
        )
    with pytest.raises(RouteDeckValidationError):
        engine.open(
            initial,
            node_id="catalog.product",
            route_params={"product_handle": "cart_private_123"},
            public_key_validator=CatalogValidator(),
        )

    opened = engine.open(
        initial,
        node_id="catalog.product",
        route_params={"product_handle": "t-shirt"},
        public_key_validator=CatalogValidator(),
    )
    assert opened.current.node_id == "catalog.product"
    assert initial.current.node_id == "catalog.browse"


def test_cancel_has_its_own_history_transition_when_back_is_disabled() -> None:
    app = compile_medusa_app_spec()
    nodes = tuple(
        node.model_copy(
            update={
                "navigation": node.navigation.model_copy(
                    update={"can_back": False, "can_cancel": True}
                )
            }
        )
        if node.id == "catalog.product"
        else node
        for node in app.spec.nodes
    )
    engine = NavigationEngine(
        replace(app, spec=app.spec.model_copy(update={"nodes": nodes}))
    )
    browsed = session_factory(app=engine.app, node_id="catalog.browse")
    product = engine.open(
        browsed,
        node_id="catalog.product",
        route_params={"product_handle": "t-shirt"},
        public_key_validator=CatalogValidator(),
    )

    cancelled = engine.cancel(
        product,
        public_key_validator=CatalogValidator(),
    )

    assert cancelled.current.node_id == "catalog.browse"
    assert cancelled.session_version == product.session_version + 1
    assert cancelled.projection_version == product.projection_version + 1
    assert cancelled.event_cursor == product.event_cursor
    empty = session_factory(
        app=engine.app,
        node_id="catalog.product",
        route_params=(LocationParameter(name="product_handle", value="t-shirt"),),
    )
    assert (
        engine.cancel(
            empty,
            public_key_validator=CatalogValidator(),
        )
        is empty
    )


def test_cancel_explicit_target_is_resolved_from_the_compiled_graph() -> None:
    app = compile_medusa_app_spec()
    nodes = tuple(
        node.model_copy(
            update={
                "navigation": node.navigation.model_copy(
                    update={
                        "can_back": False,
                        "can_cancel": True,
                        "cancel_target": NodeRef(id="buyer.home"),
                    }
                )
            }
        )
        if node.id == "catalog.product"
        else node
        for node in app.spec.nodes
    )
    engine = NavigationEngine(
        replace(app, spec=app.spec.model_copy(update={"nodes": nodes}))
    )
    product = session_factory(
        app=engine.app,
        node_id="catalog.product",
        route_params=(LocationParameter(name="product_handle", value="t-shirt"),),
    )

    cancelled = engine.cancel(
        product,
        public_key_validator=CatalogValidator(),
    )

    assert cancelled.current.node_id == "buyer.home"
    assert cancelled.back_stack == (product.current,)
    assert cancelled.session_version == product.session_version + 1
    assert cancelled.event_cursor == product.event_cursor


def test_navigation_rejects_an_incompatible_navgraph_session() -> None:
    app = compile_medusa_app_spec()
    stale = session_factory(node_id="buyer.home")

    with pytest.raises(RouteDeckValidationError, match="session_upgrade_required"):
        NavigationEngine(app).open(stale, node_id="catalog.browse")


@pytest.mark.parametrize(
    ("node_id", "route_params"),
    (
        ("cart.summary", None),
        (
            "orders.confirmation",
            {"confirmation_handle": "confirmation"},
        ),
    ),
)
def test_session_bound_navigation_requires_a_valid_same_session_capability(
    node_id: str,
    route_params: dict[str, str] | None,
) -> None:
    app = compile_medusa_app_spec()
    engine = NavigationEngine(app)
    initial = session_factory(app=app, node_id="buyer.home")

    with pytest.raises(CapabilityMismatch):
        engine.open(
            initial,
            node_id=node_id,
            route_params=route_params,
        )

    route_bindings = (
        (
            LocationParameter(
                name="confirmation_handle",
                value="confirmation",
            ),
        )
        if node_id == "orders.confirmation"
        else ()
    )
    forged = RouteResumeCapability(
        handle="resume-capability",
        session_id="another-session",
        node_id=node_id,
        expires_at=NOW + timedelta(minutes=5),
        route_params=route_bindings,
    )
    forged_session = initial.model_copy(
        update={
            "private_state": initial.private_state.model_copy(
                update={"resume_capabilities": (forged,)}
            )
        }
    )
    with pytest.raises(CapabilityMismatch):
        engine.open(
            forged_session,
            node_id=node_id,
            route_params=route_params,
            resume_handle=forged.handle,
            now=NOW,
        )

    capability = forged.model_copy(update={"session_id": initial.session_id})
    valid_session = session_factory(
        app=app,
        session_id=initial.session_id,
        node_id="buyer.home",
        resume_capabilities=(capability,),
    )
    opened = engine.open(
        valid_session,
        node_id=node_id,
        route_params=route_params,
        resume_handle=capability.handle,
        now=NOW,
    )

    assert opened.current.node_id == node_id
    assert opened.current.route_params == route_bindings
    assert opened.session_version == valid_session.session_version + 1
    assert opened.event_cursor == valid_session.event_cursor


def test_history_navigation_rejects_unknown_and_unbound_destinations() -> None:
    app = compile_medusa_app_spec()
    engine = NavigationEngine(app)
    initial = session_factory(app=app, node_id="buyer.home")

    unknown_forward = initial.model_copy(
        update={"forward_stack": (Location(node_id="missing.node"),)}
    )
    with pytest.raises(RouteDeckValidationError):
        engine.forward(unknown_forward)

    unbound_cart = initial.model_copy(
        update={"back_stack": (Location(node_id="cart.summary"),)}
    )
    with pytest.raises(RouteDeckValidationError):
        engine.back(unbound_cart, now=NOW)
    with pytest.raises(RouteDeckValidationError):
        engine.cancel(unbound_cart, now=NOW)


def test_history_navigation_revalidates_public_route_bindings() -> None:
    app = compile_medusa_app_spec()
    engine = NavigationEngine(app)
    forged_product = Location(
        node_id="catalog.product",
        route_params=(
            LocationParameter(
                name="product_handle",
                value="prod_private_123",
            ),
        ),
    )
    session = session_factory(app=app, node_id="catalog.browse").model_copy(
        update={"forward_stack": (forged_product,)}
    )

    with pytest.raises(RouteDeckValidationError):
        engine.forward(
            session,
            public_key_validator=CatalogValidator(),
        )


def test_open_rejects_an_invalid_current_location_before_pushing_history() -> None:
    app = compile_medusa_app_spec()
    invalid_current = session_factory(app=app, node_id="catalog.product")

    with pytest.raises(RouteDeckValidationError):
        NavigationEngine(app).open(
            invalid_current,
            node_id="buyer.home",
            public_key_validator=CatalogValidator(),
        )
