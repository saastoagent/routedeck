from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_projection_endpoint_is_product_owned_and_read_only() -> None:
    from app import app

    client = TestClient(app)

    response = client.get("/api/medusa-agent/projection")

    assert response.status_code == 200
    projection = response.json()
    assert projection["graph_node"] == "home"
    assert projection["surfaces"]["active"]["surface_id"] == "home.chat"
    assert projection["legal_operations"] == []
    assert projection["surface_affordances"] == []
    assert projection["navgraph"]["reachable"] == ["browse"]
    assert projection["navigation"]["current"]["deeplink"]["url"] == "/"

    assert client.post("/api/medusa-agent/action", json={}).status_code == 404
    assert client.post("/api/medusa-agent/inspect", json={}).status_code == 404
    assert client.get("/api/routedeck/projection").status_code == 404


def test_projection_uses_product_paths_and_surface_query_state() -> None:
    from app import app

    client = TestClient(app)

    response = client.get(
        "/api/medusa-agent/projection",
        params={"path": "/detail/t-shirt", "surface_id": "detail.product_detail"},
    )

    assert response.status_code == 200
    projection = response.json()
    assert projection["graph_node"] == "detail"
    assert projection["surfaces"]["active"]["surface_id"] == "detail.product_detail"
    assert projection["navigation"]["current"]["deeplink"]["url"] == "/detail/t-shirt?surface_id=detail.product_detail"
    assert projection["presentation_state"]["product_handle"] == "t-shirt"

    node_urls = [node["deeplink"]["url"] for node in projection["navgraph"]["nodes"]]
    assert "/" in node_urls
    assert "/browse" in node_urls
    assert "/detail/t-shirt" in node_urls
    assert "/cart" in node_urls
    assert all("rd_node" not in url for url in node_urls)
    assert "prod_" not in str(projection)
    assert "variant_" not in str(projection)
    assert "cart_" not in str(projection)
