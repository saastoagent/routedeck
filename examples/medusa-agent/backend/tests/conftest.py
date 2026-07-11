from __future__ import annotations

import pytest

from medusa_agent.session import BuyerMarket
from support.medusa import buyer_market as make_buyer_market


@pytest.fixture
def buyer_market() -> BuyerMarket:
    return make_buyer_market()
