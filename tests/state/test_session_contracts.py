from __future__ import annotations

import pytest
from pydantic import ValidationError

from routedeck_core.contracts.projection import FrozenJson, PublicEntityHandle
from routedeck_core.contracts.conversation import (
    ConversationRole,
    ConversationTurnStatus,
    FinalizedConversationTurn,
)
from routedeck_core.contracts.session import (
    Location,
    LocationParameter,
    PrivateDraft,
    PrivateFieldValue,
    PrivateSessionState,
    PublicSessionState,
)
from routedeck_testing.factories import session_factory


def test_session_and_nested_private_state_are_immutable() -> None:
    session = session_factory(
        private_drafts=(
            PrivateDraft(
                form_id="contact",
                field_names=("email",),
                revision=1,
            ),
        )
    )

    with pytest.raises(ValidationError):
        session.current = Location(node_id="catalog.browse")  # type: ignore[misc]
    with pytest.raises(ValidationError):
        session.private_state.drafts[0].form_id = "changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        session.back_stack.append(Location(node_id="catalog.browse"))  # type: ignore[attr-defined]


def test_nested_json_and_route_parameters_are_deeply_immutable() -> None:
    source = {"nested": {"items": ["original"]}}
    private_value = PrivateFieldValue(name="payload", value=source)
    source["nested"]["items"].append("mutated")

    assert private_value.value.to_python() == {"nested": {"items": ["original"]}}

    thawed = private_value.value.to_python()
    thawed["nested"]["items"].append("local-copy")
    assert private_value.value.to_python() == {"nested": {"items": ["original"]}}

    location = Location(
        node_id="catalog.product",
        route_params=(LocationParameter(name="product_handle", value="t-shirt"),),
    )
    with pytest.raises(ValidationError):
        location.route_params[0].value = "changed"  # type: ignore[misc]


def test_session_contracts_forbid_undeclared_fields() -> None:
    with pytest.raises(ValidationError):
        Location.model_validate({"node_id": "buyer.home", "undeclared": "not-allowed"})

    with pytest.raises(ValidationError):
        PrivateDraft.model_validate(
            {"form_id": "contact", "field_names": [], "plaintext": "not-allowed"}
        )


def test_private_form_values_never_enter_the_canonical_snapshot() -> None:
    sentinel = "private-form-sentinel@example.test"

    session = session_factory(contact_email=sentinel)
    serialized = session.model_dump_json()

    assert sentinel not in serialized
    assert session.private_state.drafts == (
        PrivateDraft(
            form_id="contact",
            field_names=("email",),
            revision=1,
        ),
    )


def test_canonical_keyed_collections_reject_duplicate_identities() -> None:
    duplicate_draft = PrivateDraft(
        form_id="contact",
        field_names=("email",),
        revision=1,
    )
    with pytest.raises(ValidationError):
        PrivateSessionState(drafts=(duplicate_draft, duplicate_draft))

    duplicate_handle = PublicEntityHandle(
        entity_kind="product",
        handle="product-handle-1",
    )
    with pytest.raises(ValidationError):
        PublicSessionState(entity_handles=(duplicate_handle, duplicate_handle))


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_frozen_json_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(TypeError):
        FrozenJson(value)


def test_session_rejects_duplicate_conversation_turn_ids() -> None:
    turn = FinalizedConversationTurn(
        turn_id="turn-1",
        role=ConversationRole.USER,
        content="hello",
        status=ConversationTurnStatus.FINALIZED,
    )
    session = session_factory()
    payload = session.model_dump()
    payload["conversation"] = (turn, turn)

    with pytest.raises(ValidationError):
        type(session).model_validate(payload)
