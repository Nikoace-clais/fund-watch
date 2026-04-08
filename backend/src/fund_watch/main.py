"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .external import close_shared_client
from .repositories.fund_repo import init_db
from .routers import funds_router, health_router
from .routers.import_ import router as import_router


# Configure logging
class ColoredFormatter(logging.Formatter):
    """Colored log formatter."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        return super().format(record)


def setup_logging():
    """Setup application logging."""
    # Create formatter
    formatter = ColoredFormatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Setup console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []
    root_logger.addHandler(handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.error').setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger('fund-watch')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting Fund Watch API")
    # Startup
    init_db()
    logger.info("✅ Database initialized")
    yield
    # Shutdown
    logger.info("🛑 Shutting down...")
    await close_shared_client()
    logger.info("👋 Goodbye!")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Fund Watch API",
        description="A-share fund valuation monitoring and portfolio management",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if logging.getLogger().level == logging.DEBUG else None,
        redoc_url="/redoc" if logging.getLogger().level == logging.DEBUG else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log incoming requests."""
        import time
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        status = response.status_code
        
        # Color status code
        status_color = "\033[32m" if status < 300 else "\033[33m" if status < 400 else "\033[31m"
        
        logger.info(
            f"{request.method:6} {request.url.path:30} "
            f"{status_color}{status}{'\033[0m':4} "
            f"{duration*1000:6.1f}ms"
        )
        
        return response
    
    # Register routers
    app.include_router(health_router)
    app.include_router(funds_router)
    app.include_router(import_router)
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
