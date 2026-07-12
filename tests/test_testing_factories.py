from __future__ import annotations

from pathlib import Path

from routedeck_testing.factories import session_factory


def test_session_factory_is_product_neutral_and_accepts_explicit_bindings() -> None:
    session = session_factory(
        private_entity_id="private-test-record",
        public_entity_handle="public-test-record",
        entity_kind="test.record",
        allowed_operation_ids=("test.open",),
    )

    assert session.private_state.entity_bindings[0].entity_kind == "test.record"
    assert session.private_state.entity_bindings[0].allowed_operation_ids == (
        "test.open",
    )
    source = Path(session_factory.__code__.co_filename).read_text(encoding="utf-8")
    assert "catalog." not in source
    assert "cart." not in source
