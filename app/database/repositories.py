# app/database/repositories.py
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload
import logging
from uuid import UUID

from app.database.models import (
    User, SearchRequest, ContentSource, CostRecord, ApiUsage,
    CacheEntry, SystemMetric, DailyStats, ErrorLog, RateLimitRecord,
    RequestStatus
)

logger = logging.getLogger(__name__)

class BaseRepository:
    """Base repository with common database operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def commit(self):
        """Commit the session"""
        await self.session.commit()
    
    async def rollback(self):
        """Rollback the session"""
        await self.session.rollback()

class UserRepository(BaseRepository):
    """Repository for User operations"""
    
    async def create_user(self, user_identifier: str, user_type: str = "anonymous", 
                         api_key: Optional[str] = None) -> User:
        """Create a new user"""
        user = User(
            user_identifier=user_identifier,
            user_type=user_type,
            api_key=api_key
        )
        self.session.add(user)
        await self.session.flush()
        return user
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_identifier(self, user_identifier: str) -> Optional[User]:
        """Get user by identifier"""
        result = await self.session.execute(
            select(User).where(User.user_identifier == user_identifier)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """Get user by API key"""
        result = await self.session.execute(
            select(User).where(User.api_key == api_key)
        )
        return result.scalar_one_or_none()
    
    async def update_last_request(self, user_id: UUID) -> None:
        """Update user's last request timestamp"""
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_request_at=func.now())
        )
    
    async def get_active_users(self, limit: int = 100) -> List[User]:
        """Get active users"""
        result = await self.session.execute(
            select(User)
            .where(User.is_active == True)
            .limit(limit)
        )
        return result.scalars().all()

class SearchRequestRepository(BaseRepository):
    """Repository for SearchRequest operations"""
    
    async def create_search_request(self, request_id: str, user_id: Optional[UUID],
                                  original_query: str, max_results: int = 8,
                                  client_ip: Optional[str] = None,
                                  user_agent: Optional[str] = None) -> SearchRequest:
        """Create a new search request"""
        search_request = SearchRequest(
            request_id=request_id,
            user_id=user_id,
            original_query=original_query,
            max_results=max_results,
            client_ip=client_ip,
            user_agent=user_agent
        )
        self.session.add(search_request)
        await self.session.flush()
        return search_request
    
    async def update_search_request(self, request_id: str, **kwargs) -> Optional[SearchRequest]:
        """Update search request with response data"""
        result = await self.session.execute(
            update(SearchRequest)
            .where(SearchRequest.request_id == request_id)
            .values(**kwargs)
            .returning(SearchRequest)
        )
        return result.scalar_one_or_none()
    
    async def get_search_request_by_id(self, request_id: str) -> Optional[SearchRequest]:
        """Get search request by request ID"""
        result = await self.session.execute(
            select(SearchRequest)
            .options(
                selectinload(SearchRequest.content_sources),
                selectinload(SearchRequest.cost_records),
                selectinload(SearchRequest.api_usage_records)
            )
            .where(SearchRequest.request_id == request_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_requests(self, user_id: UUID, limit: int = 50, 
                               offset: int = 0) -> List[SearchRequest]:
        """Get user's search requests"""
        result = await self.session.execute(
            select(SearchRequest)
            .where(SearchRequest.user_id == user_id)
            .order_by(desc(SearchRequest.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
    
    async def get_recent_requests(self, hours: int = 24, limit: int = 100) -> List[SearchRequest]:
        """Get recent search requests"""
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(SearchRequest)
            .where(SearchRequest.created_at >= since)
            .order_by(desc(SearchRequest.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_requests_by_status(self, status: RequestStatus, 
                                   limit: int = 100) -> List[SearchRequest]:
        """Get requests by status"""
        result = await self.session.execute(
            select(SearchRequest)
            .where(SearchRequest.status == status.value)
            .order_by(desc(SearchRequest.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_daily_request_count(self, date: datetime) -> int:
        """Get request count for a specific day"""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        result = await self.session.execute(
            select(func.count(SearchRequest.id))
            .where(and_(
                SearchRequest.created_at >= start_date,
                SearchRequest.created_at < end_date
            ))
        )
        return result.scalar() or 0

class ContentSourceRepository(BaseRepository):
    """Repository for ContentSource operations"""
    
    async def create_content_source(self, search_request_id: UUID, url: str,
                                  title: Optional[str] = None, content: Optional[str] = None,
                                  **kwargs) -> ContentSource:
        """Create a new content source"""
        content_source = ContentSource(
            search_request_id=search_request_id,
            url=url,
            title=title,
            content=content,
            **kwargs
        )
        self.session.add(content_source)
        await self.session.flush()
        return content_source
    
    async def get_sources_by_request(self, search_request_id: UUID) -> List[ContentSource]:
        """Get content sources for a search request"""
        result = await self.session.execute(
            select(ContentSource)
            .where(ContentSource.search_request_id == search_request_id)
            .order_by(desc(ContentSource.confidence_score))
        )
        return result.scalars().all()
    
    async def get_successful_sources(self, search_request_id: UUID) -> List[ContentSource]:
        """Get successfully fetched content sources"""
        result = await self.session.execute(
            select(ContentSource)
            .where(and_(
                ContentSource.search_request_id == search_request_id,
                ContentSource.fetch_successful == True
            ))
            .order_by(desc(ContentSource.confidence_score))
        )
        return result.scalars().all()

class CostRecordRepository(BaseRepository):
    """Repository for CostRecord operations"""
    
    async def create_cost_record(self, search_request_id: UUID, user_id: Optional[UUID],
                               **cost_data) -> CostRecord:
        """Create a new cost record"""
        cost_record = CostRecord(
            search_request_id=search_request_id,
            user_id=user_id,
            **cost_data
        )
        self.session.add(cost_record)
        await self.session.flush()
        return cost_record
    
    async def get_user_daily_cost(self, user_id: UUID, date: datetime) -> float:
        """Get user's total cost for a specific day"""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        result = await self.session.execute(
            select(func.sum(CostRecord.total_cost))
            .where(and_(
                CostRecord.user_id == user_id,
                CostRecord.created_at >= start_date,
                CostRecord.created_at < end_date
            ))
        )
        return result.scalar() or 0.0
    
    async def get_daily_cost_breakdown(self, date: datetime) -> Dict[str, float]:
        """Get daily cost breakdown by service"""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        result = await self.session.execute(
            select(
                func.sum(CostRecord.brave_search_cost).label('brave_search'),
                func.sum(CostRecord.bing_search_cost).label('bing_search'),
                func.sum(CostRecord.zenrows_cost).label('zenrows'),
                func.sum(CostRecord.llm_cost).label('llm'),
                func.sum(CostRecord.total_cost).label('total')
            )
            .where(and_(
                CostRecord.created_at >= start_date,
                CostRecord.created_at < end_date
            ))
        )
        row = result.first()
        return {
            'brave_search': row.brave_search or 0.0,
            'bing_search': row.bing_search or 0.0,
            'zenrows': row.zenrows or 0.0,
            'llm': row.llm or 0.0,
            'total': row.total or 0.0
        }

class ApiUsageRepository(BaseRepository):
    """Repository for ApiUsage operations"""
    
    async def create_api_usage(self, provider: str, search_request_id: Optional[UUID] = None,
                             **usage_data) -> ApiUsage:
        """Create a new API usage record"""
        api_usage = ApiUsage(
            provider=provider,
            search_request_id=search_request_id,
            **usage_data
        )
        self.session.add(api_usage)
        await self.session.flush()
        return api_usage
    
    async def get_provider_usage_stats(self, provider: str, 
                                     hours: int = 24) -> Dict[str, Any]:
        """Get usage statistics for a specific provider"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.session.execute(
            select(
                func.count(ApiUsage.id).label('total_calls'),
                func.count().filter(ApiUsage.success == True).label('successful_calls'),
                func.avg(ApiUsage.response_time).label('avg_response_time'),
                func.sum(ApiUsage.cost).label('total_cost')
            )
            .where(and_(
                ApiUsage.provider == provider,
                ApiUsage.created_at >= since
            ))
        )
        row = result.first()
        return {
            'total_calls': row.total_calls or 0,
            'successful_calls': row.successful_calls or 0,
            'success_rate': (row.successful_calls / row.total_calls * 100) if row.total_calls else 0,
            'avg_response_time': row.avg_response_time or 0,
            'total_cost': row.total_cost or 0
        }

class CacheRepository(BaseRepository):
    """Repository for CacheEntry operations"""
    
    async def create_cache_entry(self, cache_key: str, cache_type: str,
                               data_size: Optional[int] = None, ttl: Optional[int] = None) -> CacheEntry:
        """Create a new cache entry record"""
        expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl else None
        
        cache_entry = CacheEntry(
            cache_key=cache_key,
            cache_type=cache_type,
            data_size=data_size,
            ttl=ttl,
            expires_at=expires_at
        )
        self.session.add(cache_entry)
        await self.session.flush()
        return cache_entry
    
    async def update_cache_hit(self, cache_key: str, cache_type: str) -> None:
        """Update cache hit count"""
        await self.session.execute(
            update(CacheEntry)
            .where(and_(
                CacheEntry.cache_key == cache_key,
                CacheEntry.cache_type == cache_type
            ))
            .values(
                hit_count=CacheEntry.hit_count + 1,
                last_accessed=func.now()
            )
        )
    
    async def get_cache_stats(self, cache_type: Optional[str] = None, 
                            hours: int = 24) -> Dict[str, Any]:
        """Get cache statistics"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(
            func.count(CacheEntry.id).label('total_entries'),
            func.sum(CacheEntry.hit_count).label('total_hits'),
            func.avg(CacheEntry.data_size).label('avg_size')
        ).where(CacheEntry.created_at >= since)
        
        if cache_type:
            query = query.where(CacheEntry.cache_type == cache_type)
        
        result = await self.session.execute(query)
        row = result.first()
        
        return {
            'total_entries': row.total_entries or 0,
            'total_hits': row.total_hits or 0,
            'avg_size': row.avg_size or 0
        }

class MetricsRepository(BaseRepository):
    """Repository for SystemMetric operations"""
    
    async def create_metric(self, metric_name: str, metric_type: str, value: float,
                          labels: Optional[Dict] = None, metadata: Optional[Dict] = None) -> SystemMetric:
        """Create a new system metric"""
        metric = SystemMetric(
            metric_name=metric_name,
            metric_type=metric_type,
            value=value,
            labels=labels,
            metadata=metadata
        )
        self.session.add(metric)
        await self.session.flush()
        return metric
    
    async def get_metrics(self, metric_name: str, hours: int = 24, 
                        limit: int = 1000) -> List[SystemMetric]:
        """Get metrics for a specific metric name"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.session.execute(
            select(SystemMetric)
            .where(and_(
                SystemMetric.metric_name == metric_name,
                SystemMetric.created_at >= since
            ))
            .order_by(desc(SystemMetric.created_at))
            .limit(limit)
        )
        return result.scalars().all()

class StatsRepository(BaseRepository):
    """Repository for DailyStats operations"""
    
    async def create_or_update_daily_stats(self, date: datetime, **stats_data) -> DailyStats:
        """Create or update daily statistics"""
        # Try to get existing stats for the date
        result = await self.session.execute(
            select(DailyStats).where(
                func.date(DailyStats.date) == date.date()
            )
        )
        daily_stats = result.scalar_one_or_none()
        
        if daily_stats:
            # Update existing stats
            for key, value in stats_data.items():
                if hasattr(daily_stats, key):
                    setattr(daily_stats, key, value)
            daily_stats.updated_at = func.now()
        else:
            # Create new stats
            daily_stats = DailyStats(date=date, **stats_data)
            self.session.add(daily_stats)
        
        await self.session.flush()
        return daily_stats
    
    async def get_daily_stats(self, date: datetime) -> Optional[DailyStats]:
        """Get daily statistics for a specific date"""
        result = await self.session.execute(
            select(DailyStats).where(
                func.date(DailyStats.date) == date.date()
            )
        )
        return result.scalar_one_or_none()
    
    async def get_stats_range(self, start_date: datetime, 
                            end_date: datetime) -> List[DailyStats]:
        """Get daily statistics for a date range"""
        result = await self.session.execute(
            select(DailyStats)
            .where(and_(
                DailyStats.date >= start_date,
                DailyStats.date <= end_date
            ))
            .order_by(asc(DailyStats.date))
        )
        return result.scalars().all()

class ErrorRepository(BaseRepository):
    """Repository for ErrorLog operations"""
    
    async def log_error(self, error_type: str, error_message: str,
                       request_id: Optional[str] = None, user_id: Optional[UUID] = None,
                       **context_data) -> ErrorLog:
        """Log an error"""
        error_log = ErrorLog(
            error_type=error_type,
            error_message=error_message,
            request_id=request_id,
            user_id=user_id,
            context_data=context_data
        )
        self.session.add(error_log)
        await self.session.flush()
        return error_log
    
    async def get_recent_errors(self, hours: int = 24, limit: int = 100) -> List[ErrorLog]:
        """Get recent errors"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.session.execute(
            select(ErrorLog)
            .where(ErrorLog.created_at >= since)
            .order_by(desc(ErrorLog.created_at))
            .limit(limit)
        )
        return result.scalars().all()

class RateLimitRepository(BaseRepository):
    """Repository for RateLimitRecord operations"""
    
    async def record_rate_limit(self, identifier: str, limit_type: str,
                              window_start: datetime, window_end: datetime,
                              limit_exceeded: bool = False) -> RateLimitRecord:
        """Record a rate limit event"""
        record = RateLimitRecord(
            identifier=identifier,
            limit_type=limit_type,
            window_start=window_start,
            window_end=window_end,
            limit_exceeded=limit_exceeded
        )
        self.session.add(record)
        await self.session.flush()
        return record
    
    async def get_rate_limit_violations(self, hours: int = 24) -> List[RateLimitRecord]:
        """Get recent rate limit violations"""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.session.execute(
            select(RateLimitRecord)
            .where(and_(
                RateLimitRecord.limit_exceeded == True,
                RateLimitRecord.created_at >= since
            ))
            .order_by(desc(RateLimitRecord.created_at))
        )
        return result.scalars().all()
