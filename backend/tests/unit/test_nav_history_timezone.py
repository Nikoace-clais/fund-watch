"""fetch_nav_history 的 eastmoney 时间戳时区回归测试。

eastmoney Data_netWorthTrend/Data_ACWorthTrend 的 x 是北京时间零点的毫秒
时间戳;naive fromtimestamp 在 UTC 部署环境下会把日期解析偏早一天。
"""

from __future__ import annotations

import os
import time
from collections.abc import Generator

import pytest
from app import fund_source

# 1609430400000 ms = 2021-01-01 00:00:00 +08:00(北京时间元旦零点)
_TS_2021_01_01_CST = 1609430400000

_PINGZHONG_TEXT = (
    'var fS_name = "测试基金";'
    "var Data_netWorthTrend = "
    f'[{{"x":{_TS_2021_01_01_CST},"y":1.234,"equityReturn":0.56}}];'
    f"var Data_ACWorthTrend = [[{_TS_2021_01_01_CST},1.567]];"
)


@pytest.fixture(autouse=True)
def _clear_caches() -> Generator[None, None, None]:
    fund_source._nav_history_cache.clear()
    yield
    fund_source._nav_history_cache.clear()


@pytest.fixture
def utc_env() -> Generator[None, None, None]:
    """模拟 UTC 部署环境(回归现场)。"""
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if old_tz is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old_tz
    time.tzset()


async def test_nav_history_dates_parsed_in_beijing_tz(utc_env, monkeypatch) -> None:
    async def _fake_text(code: str) -> str:
        return _PINGZHONG_TEXT

    monkeypatch.setattr(fund_source, "_fetch_pingzhongdata_text", _fake_text)

    history = await fund_source.fetch_nav_history("110011")

    # UTC 环境下 naive 解析会得到 2020-12-31;北京时间零点应为 2021-01-01
    assert history[0]["date"] == "2021-01-01"
    assert history[0]["nav"] == 1.234
    assert history[0]["accNav"] == 1.567
