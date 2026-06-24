"""
Configuration settings for the application.

This file manages all configuration settings using environment variables.
Settings are loaded from a .env file in the backend directory.

Production defaults are safe: debug=False, no secrets hardcoded.
For local development, set DEBUG=true in your .env file.
"""

import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic will automatically:
    1. Load values from environment variables
    2. Load values from .env file
    3. Validate that values have the correct type
    4. Provide default values where specified
    """

    # Application settings
    app_name: str = "Feature-IQ"
    debug: bool = False  # Safe default; set DEBUG=true in .env for local dev

    # Database connection
    # Format: postgresql://username:password@host:port/database_name
    database_url: str = "sqlite:///./feature_voting.db"  # SQLite for simple start

    # Security settings
    # SECRET_KEY is used to sign JWT tokens - keep this secret!
    # Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    secret_key: str = ""  # Required in production; set in .env or environment
    algorithm: str = "HS256"  # Algorithm for JWT encoding
    access_token_expire_minutes: int = 30  # Tokens expire after 30 minutes

    # CORS settings - controls which websites can access your API
    # Add your frontend URL here (e.g., http://localhost:3000)
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Initial admin user settings (created automatically on first startup)
    admin_email: str = "admin@example.com"
    admin_username: str = "admin"
    admin_password: str = ""  # Required to create bootstrap admin; set in .env
    admin_full_name: str = "System Administrator"

    # AI/LLM settings
    anthropic_api_key: str = "your-anthropic-api-key-here"
    claude_model: str = "claude-sonnet-4-5-20250929"  # Default model for agents
    max_tokens_default: int = 4000  # Default max tokens for agent responses
    temperature_default: float = 0.7  # Default temperature for agent calls

    # Embedding API settings (Voyage AI for semantic search)
    voyage_api_key: str = "your-voyage-api-key-here"  # Get key at https://dash.voyageai.com/
    # Per-request timeout (seconds) for the Voyage client. Without this the
    # client waits indefinitely, which can block a request worker long enough
    # that the platform health check fails and the instance is restarted (a 502
    # to the caller). Keep well under the platform request timeout.
    voyage_timeout_seconds: float = 20.0
    voyage_max_retries: int = 2  # Bounded retries for transient Voyage errors

    # Search API settings (for competitor research)
    brave_api_key: str = "your-brave-api-key-here"  # Get free key at https://brave.com/search/api/
    enable_web_search: bool = True  # Enable web search for competitor discovery
    competitor_research_cache_ttl_hours: int = 24  # How long cached Brave results stay fresh per competitor
    web_search_cache_ttl_seconds: int = 86400  # Per-query Brave result cache TTL (Redis)
    web_search_cache_empty_ttl_seconds: int = 3600  # Shorter TTL for empty/error responses — avoid stuck misses

    # MCP HTTP server settings
    mcp_base_url: str = "http://localhost:8001"  # Public URL of MCP server (for OAuth metadata)
    frontend_url: str = "http://localhost:5173"  # Frontend URL (for OAuth consent redirect)

    # Redis/Celery settings (for background task processing)
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""  # Defaults to redis_url if not set
    celery_result_backend: str = ""  # Defaults to redis_url if not set

    # Development mode settings for OTP bypass
    # These only activate when debug=True AND the values are non-empty/True
    dev_otp_bypass: str = ""  # Set to "000000" in .env for local dev convenience
    dev_return_otp: bool = False  # Set to true in .env to see OTPs in API responses

    # Email settings (SendGrid)
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""
    sendgrid_from_name: str = "Feature-IQ"

    # Configuration for pydantic to read from .env file
    # Use absolute path so .env is found regardless of working directory
    # (needed for MCP server launched by Claude Desktop)
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        case_sensitive=False,  # DATABASE_URL and database_url are treated the same
        extra="ignore"  # Ignore extra environment variables
    )

    def validate_for_production(self) -> None:
        """Validate that required settings are configured for production.

        Called during startup when debug=False. Fails fast with clear errors
        so misconfigurations are caught before the app serves traffic.
        """
        errors = []

        if not self.secret_key or len(self.secret_key) < 32:
            errors.append(
                "SECRET_KEY must be set and at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )

        if self.secret_key == "your-secret-key-change-this-in-production":
            errors.append("SECRET_KEY is still the old insecure default. Change it.")

        if self.anthropic_api_key == "your-anthropic-api-key-here":
            errors.append("ANTHROPIC_API_KEY is still the placeholder value.")

        if self.voyage_api_key == "your-voyage-api-key-here":
            errors.append("VOYAGE_API_KEY is still the placeholder value.")

        if errors:
            print("\n=== PRODUCTION CONFIGURATION ERRORS ===", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            print("Set DEBUG=true to run in development mode.\n", file=sys.stderr)
            raise SystemExit(1)


# Create a single instance of settings to use throughout the app
# This ensures settings are loaded once and shared everywhere
settings = Settings()
