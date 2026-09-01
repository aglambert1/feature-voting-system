"""
Main FastAPI application.

This is the entry point for the FastAPI backend.
It sets up the app, configures CORS, includes routes, and initializes the database.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.logging_config import setup_logging
from app.database import init_db, create_initial_admin
from app.api import auth, ideas, votes, submissions, products, pm_review, monitoring, competitive_agents, internal_feedback, admin, invites, evidence, api_keys, job_map, job_coverage, unified_synthesis
from app.utils.security import create_access_token

setup_logging(debug=settings.debug)
logger = logging.getLogger(__name__)

# Token refresh threshold: refresh token if it's older than this many minutes
# This creates a sliding window - any activity within 30 min of last activity keeps you logged in
TOKEN_REFRESH_THRESHOLD_MINUTES = 5


class SlidingSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that implements sliding session window for JWT tokens.

    When a valid JWT token is used that was issued more than TOKEN_REFRESH_THRESHOLD_MINUTES ago,
    a new token is issued and returned in the X-New-Access-Token response header.
    This effectively resets the session timeout on user activity.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only process if request had an Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return response

        # Only issue new token if the request was successful (not 401/403)
        if response.status_code in (401, 403):
            return response

        token = auth_header.split(" ")[1]

        try:
            # Decode the token to check its age
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm]
            )

            # Get the token's issued-at time (iat) or calculate from exp
            exp_timestamp = payload.get("exp")
            if not exp_timestamp:
                return response

            exp_time = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            issued_at = exp_time - timedelta(minutes=settings.access_token_expire_minutes)

            # Check if token is older than refresh threshold
            token_age = datetime.now(timezone.utc) - issued_at
            if token_age > timedelta(minutes=TOKEN_REFRESH_THRESHOLD_MINUTES):
                # Issue a new token with the same claims
                username = payload.get("sub")
                user_id = payload.get("user_id")

                if username and user_id:
                    new_token = create_access_token(
                        data={"sub": username, "user_id": user_id}
                    )
                    # Add new token to response header
                    response.headers["X-New-Access-Token"] = new_token
                    # Expose this header to the browser (CORS)
                    response.headers["Access-Control-Expose-Headers"] = "X-New-Access-Token"

        except JWTError:
            # Token is invalid or expired - don't issue new token
            pass

        return response


def _seed_lifecycle_statuses():
    """Seed default idea lifecycle statuses if they don't exist."""
    from app.database import SessionLocal
    from app.models.idea_lifecycle_status import IdeaLifecycleStatus

    db = SessionLocal()
    try:
        existing = db.query(IdeaLifecycleStatus).count()
        if existing == 0:
            defaults = [
                IdeaLifecycleStatus(name="On Roadmap", slug="on_roadmap", color="#3B82F6", position=1, is_default=True),
                IdeaLifecycleStatus(name="Delivered", slug="delivered", color="#10B981", position=2, is_default=True),
            ]
            db.add_all(defaults)
            db.commit()
            logger.info("Seeded default idea lifecycle statuses: On Roadmap, Delivered")
        else:
            logger.info("Idea lifecycle statuses already exist (%d)", existing)
    except Exception as e:
        logger.error("Error seeding lifecycle statuses: %s", e)
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown.

    Startup:
    - Initializes database tables
    - Creates initial admin user
    """
    # Startup
    logger.info("Starting up application...")

    # Validate production configuration before anything else
    if not settings.debug:
        settings.validate_for_production()
    else:
        logger.warning("Running in DEBUG mode — not for production use")

    init_db()
    create_initial_admin()
    _seed_lifecycle_statuses()

    yield

    # Shutdown
    logger.info("Shutting down application...")


# Create the FastAPI application instance
# title and version appear in the automatic API documentation
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Feature-IQ: AI-powered product intelligence and feature prioritization",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan
)

# Configure rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Configure CORS (Cross-Origin Resource Sharing)
# This allows your frontend (running on a different port) to access this API
# Without CORS, browsers block requests from different origins for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # Which websites can access this API
    allow_credentials=True,  # Allow cookies and authorization headers
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["X-New-Access-Token"],  # Expose token refresh header to browser
)

# Add sliding session middleware for automatic token refresh
# This must be added AFTER CORSMiddleware so CORS headers are processed first
app.add_middleware(SlidingSessionMiddleware)


# Global exception handler — log full traceback, return generic error to client
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include routers from different modules
# This adds all the routes to the app
app.include_router(auth.router)
app.include_router(ideas.router)
app.include_router(votes.router)
app.include_router(submissions.router)
app.include_router(products.router)
app.include_router(products.jobs_router)  # Queue-based job endpoints
app.include_router(pm_review.router)  # Phase 4: PM Review Queue
app.include_router(monitoring.router)  # Phase 4: Competitive Monitoring
app.include_router(competitive_agents.router)  # Agent-centric competitive intelligence
app.include_router(internal_feedback.router)  # Internal feedback import and themes
app.include_router(unified_synthesis.router)  # Phase 3: Unified synthesis
app.include_router(admin.router)  # Admin endpoints (cost tracking, etc.)
app.include_router(invites.router)  # Product invite codes and redemption
app.include_router(evidence.router)  # Evidence factbase CRUD
app.include_router(api_keys.router)  # MCP API key management
app.include_router(job_map.router)  # JTBD job map CRUD
app.include_router(job_coverage.router)  # Self-assessment + job coverage across competitors


@app.get("/")
def root():
    """
    Root endpoint - just a simple health check.

    You can test this by visiting http://localhost:8000/ in your browser.

    Returns:
        A welcome message
    """
    return {
        "message": "Welcome to the Feature-IQ API",
        "docs": "/docs",
        "version": "0.1.0"
    }


@app.get("/health")
def health_check():
    """
    Health check endpoint with database connectivity check.

    Returns status "healthy" if DB is reachable, "degraded" otherwise.
    """
    from app.database import SessionLocal
    from sqlalchemy import text

    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "unreachable"

    status = "healthy" if db_status == "connected" else "degraded"
    return {
        "status": status,
        "service": settings.app_name,
        "database": db_status,
    }


# How to run this application:
# 1. Make sure you're in the backend directory
# 2. Install dependencies: pip install -r requirements.txt
# 3. Run the server: uvicorn app.main:app --reload
# 4. Visit http://localhost:8000/docs to see the interactive API documentation
#
# The --reload flag makes the server restart automatically when you change code
# This is great for development but don't use it in production!
