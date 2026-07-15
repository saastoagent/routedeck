from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from medusa_agent.composition import compile_medusa_app_spec
from medusa_agent.features.catalog import CatalogRouteKeyValidator
from medusa_agent.session import BuyerMarket, create_medusa_session
from routedeck_core.contracts.session import RouteDeckSession
from routedeck_core.projection import ConfiguredSessionProjector, ProjectionProjector


@dataclass(frozen=True)
class _FixedClock:
    current: datetime = datetime(2029, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current


def test_medusa_home_session_uses_compiled_buyer_graph(
    buyer_market: BuyerMarket,
) -> None:
    app = compile_medusa_app_spec()
    session = create_medusa_session(
        app=app,
        session_id="session-1",
        market=buyer_market,
    )
    clock = _FixedClock()
    projection = ConfiguredSessionProjector(
        app=app,
        clock=clock,
        public_key_validator_factory=CatalogRouteKeyValidator.from_session,
    ).project(session)
    generic_projection = ProjectionProjector(
        app=app,
        public_key_validator=CatalogRouteKeyValidator.from_session(session),
        now=clock.now(),
    ).project(session)

    assert isinstance(session, RouteDeckSession)
    assert session.session_id == "session-1"
    assert session.current.node_id == app.spec.entry_node.id
    assert session.current.node_id == "buyer.home"
    assert projection.surfaces.active is None
    assert [
        action.model_dump(mode="json") for action in projection.suggested_actions
    ] == [
        {
            "action_id": "buyer.browse_products",
            "label": "Browse products",
            "operation_id": "catalog.list",
            "arguments": {},
        }
    ]
    assert set(projection.legal_operation_ids) == {"catalog.list", "cart.create"}
    assert projection == generic_projection
    assert session.navgraph_version == projection.diagnostics.navgraph_version

    private_json = session.private_state.model_dump_json()
    public_json = projection.model_dump_json()
    for value in (
        buyer_market.region_handle,
        buyer_market.country_code,
        buyer_market.currency_code,
        buyer_market.sales_channel_handle,
    ):
        assert value in private_json
        assert value not in public_json
