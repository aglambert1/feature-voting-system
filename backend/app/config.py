"""
Configuration settings for the application.

This file manages all configuration settings using environment variables.
Settings are loaded from a .env file in the backend directory.
"""

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
    app_name: str = "Feature Voting System"
    debug: bool = True

    # Database connection
    # Format: postgresql://username:password@host:port/database_name
    database_url: str = "sqlite:///./feature_voting.db"  # SQLite for simple start

    # Security settings
    # SECRET_KEY is used to sign JWT tokens - keep this secret!
    # Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"  # Algorithm for JWT encoding
    access_token_expire_minutes: int = 30  # Tokens expire after 30 minutes

    # CORS settings - controls which websites can access your API
    # Add your frontend URL here (e.g., http://localhost:3000)
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Initial admin user settings (created automatically on first startup)
    admin_email: str = "admin@example.com"
    admin_username: str = "admin"
    admin_password: str = "change-this-secure-password"
    admin_full_name: str = "System Administrator"

    # AI/LLM settings
    anthropic_api_key: str = "your-anthropic-api-key-here"
    claude_model: str = "claude-sonnet-4-5-20250929"  # Default model for agents
    max_tokens_default: int = 4000  # Default max tokens for agent responses
    temperature_default: float = 0.7  # Default temperature for agent calls

    # Development mode settings for OTP bypass
    # SECURITY WARNING: Only use in development! Never enable in production!
    dev_otp_bypass: str = "000000"  # Fixed OTP that always works in debug mode
    dev_return_otp: bool = True  # Return OTP in API response when debug=True

    # Configuration for pydantic to read from .env file
    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env file
        case_sensitive=False,  # DATABASE_URL and database_url are treated the same
        extra="ignore"  # Ignore extra environment variables
    )


# Create a single instance of settings to use throughout the app
# This ensures settings are loaded once and shared everywhere
settings = Settings()
