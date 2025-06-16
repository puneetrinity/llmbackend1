# app/database/connection.py
import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import event
from sqlalchemy.pool import NullPool
import asyncio

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Create declarative base
Base = declarative_base()

class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self):
        self.engine = None
        self.async_session_factory = None
        self._is_initialized = False
    
    async def initialize(self):
        """Initialize database connection"""
        if self._is_initialized:
            return
            
        try:
            # Create async engine
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,  # Log SQL queries in debug mode
                pool_pre_ping=True,   # Verify connections before use
                pool_recycle=3600,    # Recycle connections after 1 hour
                pool_size=20,         # Connection pool size
                max_overflow=30,      # Maximum overflow connections
                poolclass=NullPool if settings.DEBUG else None,  # No pooling in debug
                connect_args={
                    "server_settings": {
                        "application_name": "llm_search_backend",
                    }
                }
            )
            
            # Create session factory
            self.async_session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False
            )
            
            # Test connection
            async with self.engine.begin() as conn:
                await conn.execute("SELECT 1")
            
            self._is_initialized = True
            logger.info("Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def create_tables(self):
        """Create all database tables"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    async def drop_tables(self):
        """Drop all database tables (use with caution!)"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise
    
    async def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self._is_initialized:
            await self.initialize()
        
        return self.async_session_factory()
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

# Global database manager instance
db_manager = DatabaseManager()

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with db_manager.get_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_database():
    """Initialize database on startup"""
    await db_manager.initialize()
    await db_manager.create_tables()

async def close_database():
    """Close database on shutdown"""
    await db_manager.close()

# Event listeners for connection handling
@event.listens_for(db_manager.engine, "connect", once=True)
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas if using SQLite"""
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

@event.listens_for(db_manager.engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log slow queries in debug mode"""
    if settings.DEBUG:
        context._query_start_time = asyncio.get_event_loop().time()

@event.listens_for(db_manager.engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query execution time"""
    if settings.DEBUG and hasattr(context, '_query_start_time'):
        total = asyncio.get_event_loop().time() - context._query_start_time
        if total > 0.1:  # Log queries taking more than 100ms
            logger.warning(f"Slow query ({total:.3f}s): {statement[:100]}...")
