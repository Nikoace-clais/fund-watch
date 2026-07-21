"""Standalone script to trigger a snapshot pull via the running API server.

Usage:
    uv run python pull_quotes.py [--api http://127.0.0.1:8010] [--force]

Can also be called from system cron as a fallback when the in-process
scheduler is not running:
    */5 9-15 * * 1-5  cd /path/to/backend && uv run python pull_quotes.py

默认只在 A 股交易时段(交易日盘中)触发;非交易时段直接退出并打印原因,
--force 可强制拉取。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime

import httpx
from app.core import CST
from app.holidays import is_trading_day
from app.services.snapshots import in_trading_hours


def _timeout() -> float:
    """拉取超时(秒):大片基金池 30s 偏紧,默认 120s,可用 PULL_QUOTES_TIMEOUT 覆盖。"""
    return float(os.environ.get("PULL_QUOTES_TIMEOUT", "120"))


async def main(api: str, force: bool = False) -> None:
    if not force:
        now = datetime.now(CST)
        if not is_trading_day(now.date()):
            print(f"skip — {now.date()} 非交易日(周末或法定节假日),--force 可强制拉取")
            return
        if not in_trading_hours():
            now_str = now.strftime("%H:%M")
            print(f"skip — 现在 {now_str} 不在盘中时段,--force 可强制拉取")
            return
    async with httpx.AsyncClient(timeout=_timeout()) as client:
        resp = await client.post(f"{api}/api/snapshots/pull")
        resp.raise_for_status()
        data = resp.json()
    print(
        f"ok — inserted={data.get('inserted')}, codes={data.get('codes')}, "
        f"at={data.get('captured_at')}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8010")
    parser.add_argument(
        "--force", action="store_true", help="忽略交易日/盘中时段检查,强制拉取"
    )
    args = parser.parse_args()
    try:
        asyncio.run(main(args.api, args.force))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
