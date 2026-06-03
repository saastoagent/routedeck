from __future__ import annotations

import uuid


class OpaqueRefStore:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self._forward: dict[str, str] = {}
        self._reverse: dict[str, str] = {}

    def remember(self, private_id: str) -> str:
        if private_id in self._reverse:
            return self._reverse[private_id]
        public_ref = f"{self.prefix}_{uuid.uuid4().hex[:12]}"
        self._forward[public_ref] = private_id
        self._reverse[private_id] = public_ref
        return public_ref

    def resolve(self, public_ref: str) -> str:
        return self._forward[public_ref]
