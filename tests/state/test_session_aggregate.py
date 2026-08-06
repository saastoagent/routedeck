from __future__ import annotations

from datetime import UTC, datetime

import pytest

from routedeck_core.contracts.conversation import (
    ConversationRole,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.interactions import (
    RouteDeckInteractionOwnerType,
    RouteDeckInteractionState,
)
from routedeck_core.contracts.projection import ClassifiedValue, DataClassification
from routedeck_core.contracts.session import (
    Location,
    OperationState,
    PrivateDraft,
    PublicSurfaceState,
    ResumeCapabilityBinding,
)
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


def test_session_aggregate_returns_original_for_noop_mutations() -> None:
    initial = session_factory()

    unchanged = (
        RouteDeckSessionAggregate(initial)
        .enter_node(initial.current)
        .replace_history(
            current=initial.current,
            back_stack=initial.back_stack,
            forward_stack=initial.forward_stack,
        )
        .append_conversation_turns(())
        .set_interaction(initial.interaction)
        .set_operation_state(initial.operation)
        .set_public_state(initial.public_state)
        .set_private_state(initial.private_state)
        .record_public_events(0)
        .commit()
    )

    assert unchanged is initial


def test_session_aggregate_replaces_an_existing_private_draft_once() -> None:
    unrelated = PrivateDraft(
        form_id="preferences", field_names=("newsletter",), revision=1
    )
    initial_draft = PrivateDraft(
        form_id="contact", field_names=("email",), revision=1
    )
    initial = session_factory().model_copy(
        update={
            "private_state": session_factory().private_state.model_copy(
                update={"drafts": (unrelated, initial_draft)}
            )
        }
    )
    replacement = initial_draft.model_copy(update={"revision": 2})

    changed = (
        RouteDeckSessionAggregate(initial)
        .store_private_draft(initial_draft)
        .store_private_draft(replacement)
        .commit()
    )

    assert changed.private_state.drafts == (unrelated, replacement)
    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version


def test_session_aggregate_commits_each_named_private_and_public_change() -> None:
    initial = session_factory()
    turn = FinalizedConversationTurn(
        turn_id="turn-1",
        role=ConversationRole.USER,
        content="Show the catalog",
        request_id="request-1",
    )
    interaction = RouteDeckInteractionState.active(
        RouteDeckInteractionOwnerType.CHAT,
        "request-1",
    )
    operation = OperationState()
    private_state = initial.private_state.model_copy(
        update={
            "drafts": (
                PrivateDraft(
                    form_id="contact", field_names=("email",), revision=1
                ),
            )
        }
    )
    public_state = initial.public_state.model_copy(
        update={"status_message": "Ready to browse"}
    )

    changed = (
        RouteDeckSessionAggregate(initial)
        .replace_history(
            current=Location(node_id="catalog.browse", entry_id=2),
            back_stack=(initial.current,),
            forward_stack=(),
        )
        .append_conversation_turns((turn,))
        .set_interaction(interaction)
        .set_operation_state(operation)
        .set_public_state(public_state)
        .set_private_state(private_state)
        .commit()
    )

    assert changed.current.node_id == "catalog.browse"
    assert changed.conversation == (turn,)
    assert changed.interaction == interaction
    assert changed.operation == operation
    assert changed.public_state == public_state
    assert changed.private_state == private_state
    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version + 1


def test_session_aggregate_advances_only_the_event_cursor_for_public_events() -> None:
    initial = session_factory()

    changed = RouteDeckSessionAggregate(initial).record_public_events(2).commit()

    assert changed.session_version == initial.session_version
    assert changed.projection_version == initial.projection_version
    assert changed.event_cursor == initial.event_cursor + 2


def test_session_aggregate_rejects_a_negative_public_event_count() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        RouteDeckSessionAggregate(session_factory()).record_public_events(-1)


def test_private_only_surface_values_do_not_advance_projection_version() -> None:
    initial = session_factory()
    private_surface = PublicSurfaceState(
        surface_id="buyer.private-form",
        values=(
            ClassifiedValue(
                name="email",
                value="private@example.com",
                classification=DataClassification.PRIVATE,
            ),
        ),
    )
    changed = (
        RouteDeckSessionAggregate(initial)
        .set_public_state(
            initial.public_state.model_copy(
                update={"surface_state": (private_surface,)}
            )
        )
        .commit()
    )

    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version


def test_public_surface_values_advance_projection_version() -> None:
    initial = session_factory()
    public_surface = PublicSurfaceState(
        surface_id="catalog.summary",
        values=(
            ClassifiedValue(
                name="title",
                value="Catalog",
                classification=DataClassification.PUBLIC,
            ),
        ),
    )
    changed = (
        RouteDeckSessionAggregate(initial)
        .set_public_state(
            initial.public_state.model_copy(update={"surface_state": (public_surface,)})
        )
        .commit()
    )

    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version + 1


def test_current_resume_handle_change_advances_projection_version() -> None:
    initial_capability = ResumeCapabilityBinding(
        handle="resume-initial",
        session_id="session-1",
        node_id="checkout.review",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    initial = session_factory(
        node_id="checkout.review",
        resume_capabilities=(initial_capability,),
    )
    replacement = initial_capability.model_copy(update={"handle": "resume-replacement"})

    changed = (
        RouteDeckSessionAggregate(initial)
        .set_private_state(
            initial.private_state.model_copy(
                update={"resume_capabilities": (replacement,)}
            )
        )
        .commit()
    )

    assert changed.session_version == initial.session_version + 1
    assert changed.projection_version == initial.projection_version + 1
