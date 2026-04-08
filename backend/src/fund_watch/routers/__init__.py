"""API routers."""
from .funds import router as funds_router
from .health import router as health_router
from .market import router as market_router

__all__ = ["funds_router", "health_router", "market_router"]
