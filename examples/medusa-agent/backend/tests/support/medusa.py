from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from medusa_agent.session import BuyerMarket


def buyer_market() -> BuyerMarket:
    from medusa_agent.session import BuyerMarket

    return BuyerMarket(
        region_handle="private-region-sentinel",
        country_code="zx",
        currency_code="qzx",
        sales_channel_handle="private-channel-sentinel",
    )
