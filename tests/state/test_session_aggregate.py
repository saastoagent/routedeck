from __future__ import annotations

from routedeck_core.contracts.session import Location, PrivateDraft
from routedeck_core.state.aggregate import RouteDeckSessionAggregate
from routedeck_testing.factories import session_factory


def test_session_aggregate_commits_named_changes_as_one_transaction() -> None:
    initial = session_factory()

    changed = (
        RouteDeckSessionAggregate(initial)
        .store_private_draft(
            PrivateDraft(
                form_id="contact",
                field_names=("email",),
                revision=1,
            )
        )
        .enter_node(Location(node_id="catalog.browse"))
        .record_public_events(2)
        .commit()
    )

    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version + 1
    assert changed.event_cursor == initial.event_cursor + 2
    assert changed.current.node_id == "catalog.browse"
    assert changed.private_state.drafts[0].form_id == "contact"
