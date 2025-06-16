# app/database/connection.py - Fixed with optional database support
import logging
from typing import Optional, AsyncGenerator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import StaticPool
from app.config.settings import settings

logger = logging.getLogger(__name__)

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
                    conn.execute("SELECT 1")
                logger.info("✅ Database connection test successful")
            except Exception as e:
                logger.warning(f"⚠️ Database connection test failed: {e}")
                raise

    async def get_session(self) -> AsyncSession:
        """Get async database session"""
        if not self.is_available or not self.session_factory:
            raise RuntimeError("Database is not available")
        return self.session_factory()

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
    """Dependency to get database session"""
    if not db_manager.is_available:
        # Return a mock session that does nothing
        yield None
        return
    
    async with db_manager.get_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_database():
    """Initialize database tables"""
    if not db_manager.is_available:
        logger.warning("⚠️ Skipping database initialization - database not available")
        return
    
    try:
        # Import models to ensure they're registered
        from app.database import models  # noqa: F401
        
        if db_manager.async_engine:
            async with db_manager.async_engine.begin() as conn:
                # Create all tables
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables initialized")
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
        async with db_manager.get_session() as session:
            result = await session.execute("SELECT 1")
            return {
                "status": "healthy",
                "message": "Database connection successful"
            }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "message": f"Database error: {str(e)}"
        }
