# app/database/__init__.py
"""Database module initialization"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .connection import (
    Base, db_manager, get_db_session, init_database, close_database
)
from .models import (
    User, SearchRequest, ContentSource, CostRecord, ApiUsage,
    CacheEntry, SystemMetric, DailyStats, ErrorLog, RateLimitRecord,
    RequestStatus, ContentSourceType, ApiProvider
)
from .repositories import (
    UserRepository, SearchRequestRepository, ContentSourceRepository,
    CostRecordRepository, ApiUsageRepository, CacheRepository,
    MetricsRepository, StatsRepository, ErrorRepository, RateLimitRepository
)
# Import the DatabaseLogger service
from app.services.database_logger import DatabaseLogger

async def get_database_logger(session: AsyncSession = Depends(get_db_session)) -> DatabaseLogger:
    """Dependency to get database logger instance"""
    return DatabaseLogger(session)

__all__ = [
    # Connection
    "Base", "db_manager", "get_db_session", "init_database", "close_database",
    
    # Models
    "User", "SearchRequest", "ContentSource", "CostRecord", "ApiUsage",
    "CacheEntry", "SystemMetric", "DailyStats", "ErrorLog", "RateLimitRecord",
    "RequestStatus", "ContentSourceType", "ApiProvider",
    
    # Repositories
    "UserRepository", "SearchRequestRepository", "ContentSourceRepository",
    "CostRecordRepository", "ApiUsageRepository", "CacheRepository",
    "MetricsRepository", "StatsRepository", "ErrorRepository", "RateLimitRepository",
    
    # Services
    "DatabaseLogger", "get_database_logger"
]
