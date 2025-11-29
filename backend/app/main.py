from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Configure logging to both stdout and file
log_dir = Path("/app/logs")
log_dir.mkdir(exist_ok=True)

# Create formatters and handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Console handler (stdout for Docker)
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
console_handler.setFormatter(formatter)

# File handler (for admin panel)
file_handler = RotatingFileHandler(
    log_dir / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
)
file_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
file_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL), handlers=[console_handler, file_handler]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events"""
    # Startup
    logger.info(f"Starting {settings.APP_NAME}...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"CORS origins: {settings.cors_origins_list}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent subscription management platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware (order matters - applied in reverse order)
from app.middleware import (
    RateLimitMiddleware,
    QueryLoggingMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
)

# 1. Request logging (applied last, logs everything)
app.add_middleware(RequestLoggingMiddleware)

# 2. Security headers (applied to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# 3. Query logging for suspicious patterns
app.add_middleware(QueryLoggingMiddleware)

# 4. Rate limiting (applied first, blocks excessive requests)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=100,  # General limit
    requests_per_hour=1000,
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "app": settings.APP_NAME, "version": "0.1.0"}


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# Import and include routers
from app.api import (
    auth,
    mailboxes,
    subscriptions,
    ai_sandbox,
    notifications,
    optimize,
    export,
    budgets,
    categories,
    cancellation,
    reviews,
    feedback,
    providers,
    oauth,
)
from app.api.endpoints import push_notifications
from app.api.admin import (
    config as admin_config,
    announcements as admin_announcements,
    users as admin_users,
    logs as admin_logs,
    security as admin_security,
    invites as admin_invites,
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(mailboxes.router, prefix="/api/mailboxes", tags=["Mailboxes"])
app.include_router(
    subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"]
)
app.include_router(categories.router, prefix="/api/categories", tags=["Categories"])
app.include_router(
    cancellation.router, prefix="/api/cancellation", tags=["Cancellation"]
)
app.include_router(reviews.router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(feedback.router, prefix="/api", tags=["Feedback"])
app.include_router(providers.router, prefix="/api", tags=["Providers"])
app.include_router(ai_sandbox.router, prefix="/api/ai-sandbox", tags=["AI Sandbox"])
app.include_router(
    notifications.router, prefix="/api/notifications", tags=["Notifications"]
)
app.include_router(
    push_notifications.router, prefix="/api/push", tags=["Push Notifications"]
)
app.include_router(optimize.router, prefix="/api/optimize", tags=["Optimization"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["Budgets"])
app.include_router(admin_config.router, prefix="/api/admin", tags=["Admin"])
app.include_router(admin_announcements.router, prefix="/api/admin", tags=["Admin"])
app.include_router(admin_users.router, prefix="/api", tags=["Admin"])
app.include_router(admin_logs.router, prefix="/api", tags=["Admin"])
app.include_router(admin_security.router, prefix="/api", tags=["Admin"])
app.include_router(admin_invites.router, prefix="/api/admin", tags=["Admin"])
app.include_router(oauth.router, prefix="/api/oauth", tags=["OAuth"])

# Additional routers (will be added as we create them)
# from app.api import reviews, analytics, budgets
# app.include_router(reviews.router, prefix="/api/email-reviews", tags=["Email Reviews"])
# app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
# app.include_router(budgets.router, prefix="/api/budgets", tags=["Budgets"])
