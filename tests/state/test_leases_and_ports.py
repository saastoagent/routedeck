from __future__ import annotations

import inspect
from datetime import datetime
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from routedeck_core.ports.clock import Clock
from routedeck_core.ports.notifier import RouteDeckNotifier
from routedeck_core.state.leases import ExecutionClaim, TurnClaim, TurnLease


def test_turn_claim_carries_complete_request_identity() -> None:
    assert {
        "session_id",
        "expected_session_version",
        "request_id",
        "request_fingerprint",
        "owner_kind",
        "parent_turn_id",
    } <= set(TurnClaim.model_fields)
    assert TurnClaim.model_fields["parent_turn_id"].is_required() is False
    assert TurnClaim.model_config.get("frozen") is True


def test_store_write_capabilities_are_frozen_and_fenced() -> None:
    for capability_type in (TurnLease, ExecutionClaim):
        assert "fencing_token" in capability_type.model_fields
        assert capability_type.model_config.get("frozen") is True
        capability = capability_type.model_construct(fencing_token=7)
        with pytest.raises(ValidationError):
            capability.fencing_token = 8


def test_clock_and_notifier_have_small_explicit_ports() -> None:
    now = Clock.__dict__["now"]
    notify = RouteDeckNotifier.__dict__["notify"]

    assert tuple(inspect.signature(now).parameters) == ("self",)
    assert get_type_hints(now)["return"] is datetime
    assert not inspect.iscoroutinefunction(now)

    assert tuple(inspect.signature(notify).parameters) == (
        "self",
        "session_id",
        "events",
    )
    assert inspect.iscoroutinefunction(notify)
    assert get_type_hints(notify)["return"] is type(None)
