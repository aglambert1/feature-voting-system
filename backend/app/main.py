"""
Main FastAPI application.

This is the entry point for the FastAPI backend.
It sets up the app, configures CORS, includes routes, and initializes the database.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, create_initial_admin
from app.api import auth, ideas, votes, submissions, products, sessions


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
)


# Include routers from different modules
# This adds all the routes to the app
app.include_router(auth.router)
app.include_router(ideas.router)
app.include_router(votes.router)
app.include_router(submissions.router)
app.include_router(products.router)
app.include_router(products.jobs_router)  # Queue-based job endpoints
app.include_router(sessions.router)


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
