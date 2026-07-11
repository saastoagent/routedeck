from __future__ import annotations

from medusa_agent.composition import compile_medusa_app_spec
from medusa_agent.session import (
    BuyerMarket,
    create_medusa_session,
    project_medusa_session,
)
from routedeck_core.contracts.session import RouteDeckSession
from routedeck_core.projection.projector import ProjectionProjector


def test_medusa_home_session_uses_compiled_buyer_graph(
    buyer_market: BuyerMarket,
) -> None:
    app = compile_medusa_app_spec()
    session = create_medusa_session(session_id="session-1", market=buyer_market)
    projection = project_medusa_session(session)
    generic_projection = ProjectionProjector(app).project(session)

    assert isinstance(session, RouteDeckSession)
    assert session.session_id == "session-1"
    assert session.current.node_id == app.spec.entry_node.id
    assert session.current.node_id == "buyer.home"
    assert projection.surfaces["active"].component == "buyer.welcome"
    assert set(projection.legal_operation_ids) == {"catalog.list"}
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
