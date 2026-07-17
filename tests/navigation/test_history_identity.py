from __future__ import annotations

from dataclasses import dataclass

from medusa_agent.composition import compile_medusa_app
import pytest

from routedeck_core.contracts.session import Location, RouteDeckSession
from routedeck_core.navigation.engine import NavigationEngine
from routedeck_core.projection.projector import ProjectionProjector
from routedeck_core.state.aggregate import RouteDeckSessionAggregate
from routedeck_core.validation import RouteDeckValidationError
from routedeck_testing.factories import session_factory


@dataclass(frozen=True)
class CatalogValidator:
    def is_valid(self, key: str, value: str) -> bool:
        return key == "product_handle" and value == "t-shirt"


def _timeline_ids(session: RouteDeckSession) -> tuple[int, ...]:
    return tuple(
        location.entry_id
        for location in (
            *session.back_stack,
            session.current,
            *reversed(session.forward_stack),
        )
    )


def test_node_entry_ids_are_server_owned_and_monotonic() -> None:
    app = compile_medusa_app()
    engine = NavigationEngine(app)
    initial = session_factory(app=app, node_id="buyer.home")

    browsed = engine.open(initial, node_id="catalog.browse")
    product = engine.open(
        browsed,
        node_id="catalog.product",
        route_params={"product_handle": "t-shirt"},
        public_key_validator=CatalogValidator(),
    )
    backed = engine.back(product, public_key_validator=CatalogValidator())
    reopened = engine.open(backed, node_id="buyer.home")

    assert initial.current.entry_id == 1
    assert browsed.current.entry_id == 2
    assert product.current.entry_id == 3
    assert backed.current.entry_id == 2
    assert backed.forward_stack[-1].entry_id == 3
    assert reopened.current.entry_id == 4
    assert reopened.next_history_entry_id == 5

    forged = (
        RouteDeckSessionAggregate(initial)
        .enter_node(
            Location(
                node_id="catalog.browse",
                entry_id=999,
            )
        )
        .commit()
    )
    assert forged.current.entry_id == 2


def test_restore_history_entry_reconstructs_the_exact_canonical_timeline() -> None:
    app = compile_medusa_app()
    engine = NavigationEngine(app)
    home = session_factory(app=app, node_id="buyer.home")
    browsed = engine.open(home, node_id="catalog.browse")
    product = engine.open(
        browsed,
        node_id="catalog.product",
        route_params={"product_handle": "t-shirt"},
        public_key_validator=CatalogValidator(),
    )

    restored_home = engine.restore_history_entry(
        product,
        home.current.entry_id,
        public_key_validator=CatalogValidator(),
    )
    restored_browse = engine.restore_history_entry(
        restored_home,
        browsed.current.entry_id,
        public_key_validator=CatalogValidator(),
    )

    assert restored_home.current.entry_id == home.current.entry_id
    assert restored_home.back_stack == ()
    assert _timeline_ids(restored_home) == (1, 2, 3)
    assert restored_browse.current.entry_id == browsed.current.entry_id
    assert tuple(item.entry_id for item in restored_browse.back_stack) == (1,)
    assert tuple(item.entry_id for item in restored_browse.forward_stack) == (3,)
    assert _timeline_ids(restored_browse) == (1, 2, 3)
    assert (
        engine.restore_history_entry(
            product,
            product.current.entry_id,
            public_key_validator=CatalogValidator(),
        )
        is product
    )

    with pytest.raises(RouteDeckValidationError, match="history entry"):
        engine.restore_history_entry(
            product,
            404,
            public_key_validator=CatalogValidator(),
        )


def test_projection_exposes_the_current_canonical_history_entry_id() -> None:
    app = compile_medusa_app()
    session = session_factory(app=app, node_id="buyer.home")

    projection = ProjectionProjector(app).project(session)

    assert projection.navigation.current_entry_id == session.current.entry_id
