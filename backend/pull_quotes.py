from __future__ import annotations

import asyncio

from app.main import pull_snapshots


async def main() -> None:
    result = await pull_snapshots()
    print(result)


if __name__ == '__main__':
    asyncio.run(main())
