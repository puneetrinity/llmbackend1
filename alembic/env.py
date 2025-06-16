# alembic/env.py
import asyncio
import os
import sys
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your models and database configuration
from app.database.connection import Base
from app.database.models import *  # Import all models
from app.config.settings import settings

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for autogenerate support
target_metadata = Base.metadata

def get_database_url():
    """Get database URL from environment or settings"""
    # Check environment variable first (for different environments)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Convert asyncpg URL to sync for alembic (when needed)
        if "postgresql+asyncpg://" in db_url:
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        return db_url
    
    # Fallback to settings
    db_url = settings.DATABASE_URL
    if "postgresql+asyncpg://" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    return db_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        render_as_batch=False,  # PostgreSQL doesn't need batch mode
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    """Run migrations with provided connection"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations in async mode"""
    # Use async engine for migrations
    database_url = get_database_url()
    
    # Convert to async URL if needed
    if not database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    connectable = create_async_engine(
        database_url,
        poolclass=pool.NullPool,  # Don't use connection pooling for migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode"""
    asyncio.run(run_async_migrations())

# Determine which mode to run in
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
