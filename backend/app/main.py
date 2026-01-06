"""
Main FastAPI application.

This is the entry point for the FastAPI backend.
It sets up the app, configures CORS, includes routes, and initializes the database.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db, create_initial_admin
from app.api import auth, ideas, votes, submissions, products, sessions, pm_review, monitoring, competitive_agents
from app.utils.security import create_access_token

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

            # Calculate when token was issued (exp - token_lifetime)
            # Use utcfromtimestamp to match utcnow() for consistent comparison
            exp_time = datetime.utcfromtimestamp(exp_timestamp)
            issued_at = exp_time - timedelta(minutes=settings.access_token_expire_minutes)

            # Check if token is older than refresh threshold
            token_age = datetime.utcnow() - issued_at
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown.

    Startup:
    - Initializes database tables
    - Creates initial admin user
    - Loads SentenceTransformer model for embeddings

    Shutdown:
    - Cleans up model from memory
    """
    # Startup
    print("Starting up application...")
    init_db()
    create_initial_admin()

    # Load SentenceTransformer model ONCE (not on every request)
    try:
        print("Loading SentenceTransformer model (all-MiniLM-L6-v2)...")
        from sentence_transformers import SentenceTransformer
        app.state.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✓ Model loaded successfully (384 dimensions)")
    except Exception as e:
        print(f"✗ Failed to load embedding model: {e}")
        print("  (Semantic search will not be available)")
        app.state.embedding_model = None

    yield

    # Shutdown
    print("Shutting down application...")
    if hasattr(app.state, 'embedding_model'):
        del app.state.embedding_model


# Create the FastAPI application instance
# title and version appear in the automatic API documentation
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="A feature voting system for prioritizing product ideas",
    docs_url="/docs",  # Swagger UI documentation
    redoc_url="/redoc",  # ReDoc documentation
    lifespan=lifespan  # Application lifecycle management
)


# Configure CORS (Cross-Origin Resource Sharing)
# This allows your frontend (running on a different port) to access this API
# Without CORS, browsers block requests from different origins for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # Which websites can access this API
    allow_credentials=True,  # Allow cookies and authorization headers
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
    expose_headers=["X-New-Access-Token"],  # Expose token refresh header to browser
)

# Add sliding session middleware for automatic token refresh
# This must be added AFTER CORSMiddleware so CORS headers are processed first
app.add_middleware(SlidingSessionMiddleware)


# Include routers from different modules
# This adds all the routes to the app
app.include_router(auth.router)
app.include_router(ideas.router)
app.include_router(votes.router)
app.include_router(submissions.router)
app.include_router(products.router)
app.include_router(products.jobs_router)  # Queue-based job endpoints
app.include_router(sessions.router)
app.include_router(pm_review.router)  # Phase 4: PM Review Queue
app.include_router(monitoring.router)  # Phase 4: Competitive Monitoring
app.include_router(competitive_agents.router)  # Agent-centric competitive intelligence


@app.get("/")
def root():
    """
    Root endpoint - just a simple health check.

    You can test this by visiting http://localhost:8000/ in your browser.

    Returns:
        A welcome message
    """
    return {
        "message": "Welcome to the Feature Voting System API",
        "docs": "/docs",
        "version": "0.1.0"
    }


@app.get("/health")
def health_check():
    """
    Health check endpoint.

    Useful for monitoring and deployment systems to check if the API is running.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "service": settings.app_name
    }


# How to run this application:
# 1. Make sure you're in the backend directory
# 2. Install dependencies: pip install -r requirements.txt
# 3. Run the server: uvicorn app.main:app --reload
# 4. Visit http://localhost:8000/docs to see the interactive API documentation
#
# The --reload flag makes the server restart automatically when you change code
# This is great for development but don't use it in production!
