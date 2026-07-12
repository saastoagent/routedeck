from __future__ import annotations

from medusa_agent.request_ids import initial_cart_request_id


def test_initial_cart_request_id_is_stable_and_does_not_embed_session_capability() -> (
    None
):
    session_id = "guest-session-bearer-sentinel"

    first = initial_cart_request_id(session_id)
    replay = initial_cart_request_id(session_id)
    another = initial_cart_request_id("another-guest-session")

    assert first == replay
    assert first != another
    assert first.startswith("cart-create:")
    assert session_id not in first
