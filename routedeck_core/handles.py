from __future__ import annotations

import secrets


def new_opaque_handle() -> str:
    """Create a framework-owned, non-derivable public interaction handle."""

    return f"rdh_{secrets.token_urlsafe(24)}"


__all__ = ["new_opaque_handle"]
