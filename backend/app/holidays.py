"""中国法定节假日(放假日)表与 A 股交易日判断。

数据源:国务院办公厅节假日安排通知
- 2025 年:国办发明电〔2024〕12号
- 2026 年:国办发明电〔2025〕7号

注意:每年初需人工更新假日表(新一年的安排通常在前一年 11 月发布)。
"""

from __future__ import annotations

from datetime import date, timedelta


def _date_range(start: date, end: date) -> frozenset[date]:
    """生成 [start, end] 闭区间的日期集合。"""
    return frozenset(start + timedelta(days=i) for i in range((end - start).days + 1))


# 2025 年放假日
_HOLIDAYS_2025: frozenset[date] = (
    frozenset({date(2025, 1, 1)})  # 元旦
    | _date_range(date(2025, 1, 28), date(2025, 2, 4))  # 春节
    | _date_range(date(2025, 4, 4), date(2025, 4, 6))  # 清明节
    | _date_range(date(2025, 5, 1), date(2025, 5, 5))  # 劳动节
    | _date_range(date(2025, 5, 31), date(2025, 6, 2))  # 端午节
    | _date_range(date(2025, 10, 1), date(2025, 10, 8))  # 国庆节、中秋节
)

# 2026 年放假日
_HOLIDAYS_2026: frozenset[date] = (
    _date_range(date(2026, 1, 1), date(2026, 1, 3))  # 元旦
    | _date_range(date(2026, 2, 15), date(2026, 2, 23))  # 春节
    | _date_range(date(2026, 4, 4), date(2026, 4, 6))  # 清明节
    | _date_range(date(2026, 5, 1), date(2026, 5, 5))  # 劳动节
    | _date_range(date(2026, 6, 19), date(2026, 6, 21))  # 端午节
    | _date_range(date(2026, 9, 25), date(2026, 9, 27))  # 中秋节
    | _date_range(date(2026, 10, 1), date(2026, 10, 7))  # 国庆节
)

HOLIDAYS: frozenset[date] = _HOLIDAYS_2025 | _HOLIDAYS_2026


def is_trading_day(d: date) -> bool:
    """A 股交易日:周一至周五且不在法定节假日放假日集合中。

    调休上班的周六日仍非交易日(交易所周末一律休市),故只判 weekday。
    """
    return d.weekday() < 5 and d not in HOLIDAYS
