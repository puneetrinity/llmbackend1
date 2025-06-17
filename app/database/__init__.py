# app/database/__init__.py - SIMPLIFIED TO AVOID CIRCULAR IMPORTS
"""Database module initialization"""

from .connection import (
    Base, db_manager, get_db_session, init_database, close_database
)
from .models import (
    User, SearchRequest, ContentSource, CostRecord, ApiUsage,
    CacheEntry, SystemMetric, DailyStats, ErrorLog, RateLimitRecord,
    RequestStatus, ContentSourceType, ApiProvider
)

# Import repositories directly to avoid circular imports
try:
    from .repositories import (
        UserRepository, SearchRequestRepository, ContentSourceRepository,
        CostRecordRepository, ApiUsageRepository, CacheRepository,
        MetricsRepository, StatsRepository, ErrorRepository, RateLimitRepository
    )
except ImportError:
    # If repositories can't be imported due to circular dependencies, skip them
    pass

# Skip DatabaseLogger import to avoid circular imports
# It can be imported directly where needed

__all__ = [
    # Connection
    "Base", "db_manager", "get_db_session", "init_database", "close_database",
    
    # Models
    "User", "SearchRequest", "ContentSource", "CostRecord", "ApiUsage",
    "CacheEntry", "SystemMetric", "DailyStats", "ErrorLog", "RateLimitRecord",
    "RequestStatus", "ContentSourceType", "ApiProvider"
]
