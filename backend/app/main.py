"""Fund Watch API — application factory and wiring.

Routes live in app/routers/*, business logic in app/services/*,
request payload models in app/schemas.py.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .core import UPLOAD_DIR
from .db import init_db
from .fund_source import close_shared_client
from .routers import (
    ai,
    funds,
    health,
    market,
    ocr,
    portfolio,
    quotes,
    stocks,
    transactions,
)
from .services.snapshots import snapshot_scheduler

# ── Logging setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
# Show DEBUG logs from fund_source so per-request timings are visible
logging.getLogger("app.fund_source").setLevel(logging.DEBUG)
logging.getLogger(__name__).setLevel(logging.DEBUG)
logging.getLogger("app.services.ai_agent").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(snapshot_scheduler())
    logger.info("Fund Watch API started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await close_shared_client()
    logger.info("Fund Watch API shutdown")


app = FastAPI(title="Fund Watch API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - t0
    level = logging.WARNING if elapsed > 3.0 else logging.INFO
    logger.log(
        level,
        "%s %s -> %d  %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


# Order matters for overlapping paths: literal routes (e.g. POST /api/funds/batch
# in the funds router) must be registered before parameterized ones
# (POST /api/funds/{code}); within each router the declaration order preserves this.
app.include_router(health.router)
app.include_router(funds.router)
app.include_router(quotes.router)
app.include_router(portfolio.router)
app.include_router(transactions.router)
app.include_router(ai.router)
app.include_router(ocr.router)
app.include_router(market.router)
app.include_router(stocks.router)
