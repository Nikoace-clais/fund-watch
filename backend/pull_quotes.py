"""Standalone script to trigger a snapshot pull via the running API server.

Usage:
    uv run python pull_quotes.py [--api http://127.0.0.1:8010]

Can also be called from system cron as a fallback when the in-process
scheduler is not running:
    */5 9-15 * * 1-5  cd /path/to/backend && uv run python pull_quotes.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import httpx


async def main(api: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{api}/api/snapshots/pull")
        resp.raise_for_status()
        data = resp.json()
    print(f"ok — inserted={data.get('inserted')}, codes={data.get('codes')}, at={data.get('captured_at')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8010")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.api))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
