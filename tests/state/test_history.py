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


def test_back_and_forward_navigation_move_exact_history_entries() -> None:
    first = Location(node_id="buyer.home", entry_id=1)
    second = Location(node_id="catalog.browse", entry_id=2)
    current = Location(node_id="catalog.product", entry_id=3)

    back = move_back(
        current=current,
        back_stack=(first, second),
        forward_stack=(),
    )
    assert back.current == second
    assert back.back_stack == (first,)
    assert back.forward_stack == (current,)

    forward = move_forward(
        current=back.current,
        back_stack=back.back_stack,
        forward_stack=back.forward_stack,
    )
    assert forward.current == current
    assert forward.back_stack == (first, second)
    assert forward.forward_stack == ()
