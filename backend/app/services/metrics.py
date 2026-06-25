"""Simple metric helpers computed from NAV history."""
from __future__ import annotations


def max_drawdown(nav_list: list[float]) -> float:
    """Maximum peak-to-trough drawdown as a positive percentage.

    Example: 32.5 means -32.5% from peak. Returns 0.0 if fewer than 2 points.
    """
    if len(nav_list) < 2:
        return 0.0
    peak = nav_list[0]
    max_dd = 0.0
    for v in nav_list:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)
