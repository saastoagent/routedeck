from __future__ import annotations

import hashlib


_INITIAL_CART_REQUEST_DOMAIN = b"medusa-agent.initial-cart-request.v1\x00"


def initial_cart_request_id(session_id: str) -> str:
    """Derive a stable startup request ID without exposing the session bearer."""

    if not session_id:
        raise ValueError("initial cart request ID requires a session ID")
    digest = hashlib.sha256(
        _INITIAL_CART_REQUEST_DOMAIN + session_id.encode("utf-8")
    ).hexdigest()
    return f"cart-create:{digest}"


__all__ = ["initial_cart_request_id"]
