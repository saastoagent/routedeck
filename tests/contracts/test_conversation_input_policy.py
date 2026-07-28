from __future__ import annotations

import pytest
from pydantic import ValidationError

from routedeck_core.contracts.conversation import ConversationInputPolicy


def test_disabled_conversation_input_requires_product_copy() -> None:
    with pytest.raises(ValidationError, match="disabled_message"):
        ConversationInputPolicy(enabled=False)


def test_enabled_conversation_input_rejects_inapplicable_disabled_copy() -> None:
    with pytest.raises(ValidationError, match="disabled_message"):
        ConversationInputPolicy(enabled=True, disabled_message="Unavailable")


def test_disabled_conversation_input_preserves_product_copy() -> None:
    policy = ConversationInputPolicy(
        enabled=False,
        disabled_message="Chat is disabled while entering account credentials.",
    )

    assert policy.enabled is False
    assert policy.disabled_message == (
        "Chat is disabled while entering account credentials."
    )
