from __future__ import annotations

import pytest

from routedeck_core.contracts.session import Location, PrivateDraft
from routedeck_core.state.reducer import (
    NodeEntered,
    PrivateDraftStored,
    PublicEventsRecorded,
    reduce_session,
)
from routedeck_testing.factories import session_factory


def test_projection_versions_change_only_for_public_state() -> None:
    initial = session_factory()
    private_only = reduce_session(
        initial,
        PrivateDraftStored(
            draft=PrivateDraft(
                form_id="contact",
                field_names=("email",),
                revision=1,
            )
        ),
    )
    visible = reduce_session(
        private_only,
        NodeEntered(location=Location(node_id="catalog.browse")),
    )

    assert private_only.session_version == initial.session_version + 1
    assert private_only.projection_version == initial.projection_version
    assert visible.session_version == private_only.session_version + 1
    assert visible.projection_version == private_only.projection_version + 1
    assert visible.event_cursor == private_only.event_cursor


def test_semantic_noop_changes_no_version_and_returns_same_session() -> None:
    initial = session_factory(node_id="buyer.home")

    unchanged = reduce_session(
        initial,
        NodeEntered(location=Location(node_id="buyer.home")),
    )

    assert unchanged is initial
    assert (
        unchanged.session_version,
        unchanged.projection_version,
        unchanged.event_cursor,
    ) == (
        initial.session_version,
        initial.projection_version,
        initial.event_cursor,
    )


def test_repeated_identical_private_draft_is_a_semantic_noop() -> None:
    draft = PrivateDraft(
        form_id="contact",
        field_names=("email",),
        revision=1,
    )
    initial = session_factory(private_drafts=(draft,))

    unchanged = reduce_session(initial, PrivateDraftStored(draft=draft))

    assert unchanged is initial
    assert (
        unchanged.session_version,
        unchanged.projection_version,
        unchanged.event_cursor,
    ) == (
        initial.session_version,
        initial.projection_version,
        initial.event_cursor,
    )


def test_event_cursor_is_independent_and_counts_each_durable_public_event() -> None:
    initial = session_factory()

    recorded = reduce_session(initial, PublicEventsRecorded(count=3))

    assert recorded.event_cursor == initial.event_cursor + 3
    assert recorded.session_version == initial.session_version
    assert recorded.projection_version == initial.projection_version


def test_unknown_reducer_event_fails_loudly() -> None:
    with pytest.raises(TypeError):
        reduce_session(session_factory(), object())
