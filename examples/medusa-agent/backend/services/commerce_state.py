from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CommerceSessionState:
    current_node: str = "home"
    selected_product_ref: str | None = None
    selected_variant_ref: str | None = None
    cart_ref: str | None = None
    cart_items: list[dict[str, object]] = field(default_factory=list)

    def public_snapshot(self) -> dict[str, object]:
        return {
            "current_node": self.current_node,
            "selected_product_ref": self.selected_product_ref,
            "selected_variant_ref": self.selected_variant_ref,
            "cart_ref": self.cart_ref,
            "cart_items": self.cart_items,
        }


class CommerceStateStore:
    def __init__(self) -> None:
        self._sessions: dict[str, CommerceSessionState] = {}

    def for_session(self, session_id: str) -> CommerceSessionState:
        return self._sessions.setdefault(session_id, CommerceSessionState())
