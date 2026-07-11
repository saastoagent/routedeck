from __future__ import annotations

from routedeck_core.contracts.session import (
    Location,
    PrivateDraft,
)
from routedeck_core.state.reducer import (
    NodeEntered,
    PrivateDraftStored,
    PublicEventsRecorded,
    reduce_session_batch,
)
from routedeck_testing.factories import session_factory


def test_one_transaction_with_multiple_changes_increments_versions_once() -> None:
    initial = session_factory()

    changed = reduce_session_batch(
        initial,
        (
            PrivateDraftStored(
                draft=PrivateDraft(
                    form_id="contact",
                    field_names=("email",),
                    revision=1,
                )
            ),
            NodeEntered(location=Location(node_id="catalog.browse")),
            PublicEventsRecorded(count=2),
        ),
    )

    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version + 1
    assert changed.event_cursor == initial.event_cursor + 2
