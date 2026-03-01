from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import app config and models so Alembic can see the schema
from app.config import settings
from app.database import Base

# Import all models so they register with Base.metadata
import app.models.user  # noqa: F401
import app.models.idea  # noqa: F401
import app.models.vote  # noqa: F401
import app.models.competitor_intelligence  # noqa: F401
import app.models.queue  # noqa: F401
import app.models.competitive_agent  # noqa: F401
import app.models.competitive_reports  # noqa: F401
import app.models.idea_lifecycle_status  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with the app's database URL
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the app's Base metadata for autogenerate support
target_metadata = Base.metadata

# Tables managed outside of Alembic (sqlite-vec virtual tables, manual tables)
_EXCLUDED_TABLES = {
    "vec_ideas", "vec_ideas_chunks", "vec_ideas_rowids", "vec_ideas_vector_chunks00",
    "vec_products", "vec_products_chunks", "vec_products_rowids", "vec_products_vector_chunks00",
    "vec_competitor_features", "vec_competitor_features_chunks",
    "vec_competitor_features_rowids", "vec_competitor_features_vector_chunks00",
    "vec_product_features", "vec_product_features_chunks",
    "vec_product_features_rowids", "vec_product_features_vector_chunks00",
    "product_chunks",
}


def include_object(object, name, type_, reflected, compare_to):
    """Exclude vec virtual tables and related tables from autogenerate."""
    if type_ == "table" and name in _EXCLUDED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
