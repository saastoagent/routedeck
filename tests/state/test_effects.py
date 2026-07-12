from __future__ import annotations

import pytest
from pydantic import ValidationError

from routedeck_core.contracts.effects import SessionEffects
from routedeck_core.contracts.failures import FailureKind, RouteDeckFailure
from routedeck_core.contracts.operations import DeliveryPhase, OperationOutcome
from routedeck_core.contracts.session import PrivateDraft
from routedeck_core.state.effects import session_state_with_effects
from routedeck_testing.factories import session_factory


def test_session_effects_remove_only_the_named_private_form() -> None:
    session = session_factory(
        private_drafts=(
            PrivateDraft(
                form_id="contact",
                field_names=("email",),
                revision=1,
                complete=True,
            ),
            PrivateDraft(
                form_id="preferences",
                field_names=("newsletter",),
                revision=1,
                complete=True,
            ),
        )
    )

    private_state, _ = session_state_with_effects(
        session,
        SessionEffects(remove_private_form_ids=("contact",)),
    )

    assert tuple(draft.form_id for draft in private_state.drafts) == ("preferences",)


def test_private_form_removal_effects_are_exact() -> None:
    session = session_factory()

    with pytest.raises(ValueError, match="existing private forms"):
        session_state_with_effects(
            session,
            SessionEffects(remove_private_form_ids=("missing",)),
        )

    with pytest.raises(ValidationError, match="private form IDs must be unique"):
        SessionEffects(remove_private_form_ids=("contact", "contact"))


def test_session_completion_is_an_explicit_durable_effect_not_public_state() -> None:
    session = session_factory()

    effects = SessionEffects(complete_session=True)
    private_state, public_state = session_state_with_effects(session, effects)

    assert not effects.is_empty
    assert effects.model_dump(mode="json")["complete_session"] is True
    assert private_state == session.private_state
    assert public_state == session.public_state


def test_failed_operations_cannot_request_session_completion() -> None:
    with pytest.raises(
        ValidationError, match="completion requires a successful outcome"
    ):
        OperationOutcome(
            delivery_phase=DeliveryPhase.RESPONSE_RECEIVED,
            effects=SessionEffects(complete_session=True),
            failure=RouteDeckFailure(
                kind=FailureKind.BUSINESS,
                code="payment_declined",
                phase="execute",
                correlation_id="correlation-1",
                public_message="Payment was declined.",
            ),
        )
