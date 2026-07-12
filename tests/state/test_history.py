from __future__ import annotations

import pytest

from routedeck_core.contracts.session import Location
from routedeck_core.state.history import enter_location, move_back, move_forward
from routedeck_core.validation import RouteDeckValidationError


def test_entering_the_current_location_clears_forward_history_without_duplication() -> (
    None
):
    current = Location(node_id="buyer.home", entry_id=1)
    back = (Location(node_id="catalog.browse", entry_id=2),)

    history = enter_location(
        current=current,
        back_stack=back,
        location=current,
    )

    assert history.current is current
    assert history.back_stack == back
    assert history.forward_stack == ()


def test_back_navigation_without_history_fails_loudly() -> None:
    with pytest.raises(RouteDeckValidationError, match="Back navigation"):
        move_back(
            current=Location(node_id="buyer.home", entry_id=1),
            back_stack=(),
            forward_stack=(),
        )


def test_forward_navigation_without_history_fails_loudly() -> None:
    with pytest.raises(RouteDeckValidationError, match="Forward navigation"):
        move_forward(
            current=Location(node_id="buyer.home", entry_id=1),
            back_stack=(),
            forward_stack=(),
        )
