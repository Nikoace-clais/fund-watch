"""External data sources."""
from .eastmoney import (
    close_shared_client,
    fetch_fund_detail,
    fetch_fund_holdings,
    fetch_fund_info,
    fetch_latest_nav,
    fetch_market_indices,
    fetch_nav_history,
    fetch_nav_on_date,
    fetch_realtime_estimate,
    search_fund_by_name,
)

__all__ = [
    "close_shared_client",
    "fetch_fund_detail",
    "fetch_fund_holdings",
    "fetch_fund_info",
    "fetch_latest_nav",
    "fetch_market_indices",
    "fetch_nav_history",
    "fetch_nav_on_date",
    "fetch_realtime_estimate",
    "search_fund_by_name",
]
