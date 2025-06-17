# app/database/connection.py - RAILWAY DEPLOYMENT READY VERSION
import os
import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base  # FIXED: Correct import
from sqlalchemy.pool import StaticPool
from app.config.settings import settings

logger = logging.getLogger(__name__)

# DEBUG: Add debug logging
logger.info(f"🔍 DEBUG: Raw DATABASE_URL from env: {os.getenv('DATABASE_URL')}")
logger.info(f"🔍 DEBUG: Settings DATABASE_URL: {settings.DATABASE_URL}")
logger.info(f"🔍 DEBUG: Template resolved?: {settings.DATABASE_URL.startswith('postgresql://')}")

# Create declarative base
Base = declarative_base()

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.async_engine = None
        self.session_factory = None
        self.is_available = False
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize database engine with error handling"""
        try:
            database_url = settings.DATABASE_URL
            logger.info(f"🔧 Initializing database: {database_url.split('@')[0] if '@' in database_url else database_url}...")
            
            # DEBUG: Check if template variable is resolved
            if database_url.startswith("${{"):
                logger.error(f"❌ DATABASE_URL template variable not resolved: {database_url}")
                logger.error("❌ Railway template variables are not working!")
                return
            
            # Skip database if URL is not properly configured
            if not database_url or database_url == "postgresql://user:pass@localhost:5432/searchdb":
                logger.warning("⚠️ Database URL not configured, running without database")
                return
            
            # For SQLite, use synchronous engine
            if database_url.startswith("sqlite"):
                self.engine = create_engine(
                    database_url,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False},
                    echo=settings.DEBUG
                )
                # Create async engine for SQLite
                async_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
                self.async_engine = create_async_engine(
                    async_url,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False},
                    echo=settings.DEBUG
                )
            
            # For PostgreSQL
            elif database_url.startswith("postgresql"):
                # Sync engine
                self.engine = create_engine(
                    database_url,
                    pool_pre_ping=True,
                    echo=settings.DEBUG
                )
                # Async engine
                async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
                if not async_url.startswith("postgresql+asyncpg://"):
                    async_url = database_url.replace("postgresql", "postgresql+asyncpg")
                
                self.async_engine = create_async_engine(
                    async_url,
                    pool_pre_ping=True,
                    echo=settings.DEBUG
                )
            
            else:
                logger.error(f"❌ Unsupported database URL: {database_url}")
                return
            
            # Create session factory
            if self.async_engine:
                self.session_factory = async_sessionmaker(
                    self.async_engine,
                    class_=AsyncSession,
                    expire_on_commit=False
                )
            
            # Test connection
            self._test_connection()
            self.is_available = True
            logger.info("✅ Database connection established")
            
        except Exception as e:
            logger.warning(f"⚠️ Database initialization failed: {e}")
            logger.warning("⚠️ Application will run without database functionality")
            self.is_available = False

    def _test_connection(self):
        """Test database connection"""
        if self.engine:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection test successful")
            except Exception as e:
                logger.warning(f"⚠️ Database connection test failed: {e}")
                raise

    def get_session(self) -> AsyncSession:
        """Get async database session - DEPRECATED: Use get_session_context() instead"""
        if not self.is_available or not self.session_factory:
            raise RuntimeError("Database is not available")
        return self.session_factory()

    @asynccontextmanager
    async def get_session_context(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session with proper context management - THIS IS THE KEY FIX"""
        if not self.is_available or not self.session_factory:
            raise RuntimeError("Database is not available")
        
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self):
        """Close database connections"""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.engine:
            self.engine.dispose()

# Create global database manager
db_manager = DatabaseManager()

# Only set up event listeners if engine is available
if db_manager.engine is not None:
    @event.listens_for(db_manager.engine, "connect", once=True)
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set SQLite pragmas for better performance"""
        if 'sqlite' in str(dbapi_connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session - FIXED"""
    if not db_manager.is_available:
        # Return a mock session that does nothing
        yield None
        return
    
    # FIXED: Use the proper context manager
    async with db_manager.get_session_context() as session:
        yield session

async def init_database():
    """Initialize database - Railway GitHub deployment compatible"""
    if not db_manager.is_available:
        logger.warning("⚠️ Skipping database initialization - database not available")
        return
    
    try:
        # Import models to ensure they're registered
        from app.database import models  # noqa: F401
        
        if db_manager.async_engine:
            try:
                # Try migrations first (future-proof approach)
                import subprocess
                import sys
                
                logger.info("🔄 Attempting database migrations...")
                result = subprocess.run([
                    sys.executable, 
                    "scripts/manage_migrations.py", 
                    "upgrade"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    logger.info("✅ Database migrations applied successfully")
                    if result.stdout.strip():
                        logger.info(f"Migration output: {result.stdout.strip()}")
                    return  # Success with migrations
                else:
                    # Migrations failed, fall back to create_all
                    if "No migrations to apply" in (result.stderr or ""):
                        logger.info("✅ Database already up to date (no migrations needed)")
                        return
                    else:
                        logger.info("⚠️ Migrations not available or failed, using create_all")
                        
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                # Migration script not available or failed, fall back
                logger.info(f"⚠️ Migration attempt failed: {e}")
                logger.info("📋 Using create_all approach")
            
            # Fallback: Use create_all with safety checks
            try:
                async with db_manager.async_engine.begin() as conn:
                    # Create all tables with checkfirst to avoid "already exists" errors
                    await conn.run_sync(Base.metadata.create_all, checkfirst=True)
                logger.info("✅ Database tables initialized with create_all")
                
            except Exception as create_error:
                if "already exists" in str(create_error).lower():
                    logger.info("✅ Database tables already exist (no changes needed)")
                else:
                    logger.error(f"❌ Database table creation failed: {create_error}")
                    # Don't raise - let app continue, database might still work
        else:
            logger.warning("⚠️ No async engine available for database initialization")
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Don't raise the error - let the app continue without database

async def close_database():
    """Close database connections"""
    try:
        await db_manager.close()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error closing database: {e}")

# Health check function
async def check_database_health() -> dict:
    """Check database health"""
    if not db_manager.is_available:
        return {
            "status": "unavailable",
            "message": "Database not configured"
        }
    
    try:
        async with db_manager.get_session_context() as session:
            await session.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "message": "Database connection successful"
            }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "message": f"Database error: {str(e)}"
        }
