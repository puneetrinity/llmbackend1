# app/database/__init__.py
"""Database module initialization"""

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
    "MetricsRepository", "StatsRepository", "ErrorRepository", "RateLimitRepository"
]

# app/services/database_logger.py
"""Database logging service for search requests and analytics"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from app.database.repositories import (
    UserRepository, SearchRequestRepository, ContentSourceRepository,
    CostRecordRepository, ApiUsageRepository, ErrorRepository, StatsRepository
)
from app.database.models import RequestStatus, ContentSourceType, ApiProvider
from app.models.responses import SearchResponse
from app.models.internal import ContentData

logger = logging.getLogger(__name__)

class DatabaseLogger:
    """Service for logging search requests and related data to database"""
    
    def __init__(self, session):
        self.session = session
        self.user_repo = UserRepository(session)
        self.search_repo = SearchRequestRepository(session)
        self.content_repo = ContentSourceRepository(session)
        self.cost_repo = CostRecordRepository(session)
        self.api_repo = ApiUsageRepository(session)
        self.error_repo = ErrorRepository(session)
        self.stats_repo = StatsRepository(session)
    
    async def log_search_request(
        self,
        request_id: str,
        user_identifier: Optional[str],
        original_query: str,
        max_results: int = 8,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UUID:
        """Log a new search request and return the database ID"""
        try:
            # Get or create user
            user_id = None
            if user_identifier:
                user = await self.user_repo.get_user_by_identifier(user_identifier)
                if not user:
                    user = await self.user_repo.create_user(
                        user_identifier=user_identifier,
                        user_type="anonymous"
                    )
                user_id = user.id
                
                # Update last request time
                await self.user_repo.update_last_request(user_id)
            
            # Create search request
            search_request = await self.search_repo.create_search_request(
                request_id=request_id,
                user_id=user_id,
                original_query=original_query,
                max_results=max_results,
                client_ip=client_ip,
                user_agent=user_agent
            )
            
            await self.session.commit()
            logger.info(f"Logged search request: {request_id}")
            return search_request.id
            
        except Exception as e:
            logger.error(f"Failed to log search request: {e}")
            await self.session.rollback()
            raise
    
    async def update_search_response(
        self,
        request_id: str,
        response: SearchResponse,
        enhanced_queries: Optional[List[str]] = None,
        status: RequestStatus = RequestStatus.COMPLETED
    ):
        """Update search request with response data"""
        try:
            await self.search_repo.update_search_request(
                request_id=request_id,
                enhanced_queries=enhanced_queries,
                status=status.value,
                response_answer=response.answer,
                response_sources=response.sources,
                confidence_score=response.confidence,
                processing_time=response.processing_time,
                cache_hit=response.cached,
                total_cost=response.cost_estimate or 0.0,
                completed_at=datetime.utcnow()
            )
            
            await self.session.commit()
            logger.info(f"Updated search response: {request_id}")
            
        except Exception as e:
            logger.error(f"Failed to update search response: {e}")
            await self.session.rollback()
            raise
    
    async def log_content_sources(
        self,
        search_request_id: UUID,
        content_data: List[ContentData]
    ):
        """Log content sources for a search request"""
        try:
            for content in content_data:
                await self.content_repo.create_content_source(
                    search_request_id=search_request_id,
                    url=content.url,
                    title=content.title,
                    content=content.content[:5000],  # Truncate long content
                    word_count=content.word_count,
                    source_type=content.source_type.value,
                    extraction_method=content.extraction_method,
                    confidence_score=content.confidence_score,
                    fetch_time=content.fetch_time,
                    fetch_successful=True if content.content else False
                )
            
            await self.session.commit()
            logger.info(f"Logged {len(content_data)} content sources")
            
        except Exception as e:
            logger.error(f"Failed to log content sources: {e}")
            await self.session.rollback()
            raise
    
    async def log_cost_record(
        self,
        search_request_id: UUID,
        user_id: Optional[UUID],
        cost_breakdown: Dict[str, float],
        usage_counts: Dict[str, int]
    ):
        """Log cost record for a search request"""
        try:
            await self.cost_repo.create_cost_record(
                search_request_id=search_request_id,
                user_id=user_id,
                brave_search_cost=cost_breakdown.get('brave_search', 0.0),
                bing_search_cost=cost_breakdown.get('bing_search', 0.0),
                bing_autosuggest_cost=cost_breakdown.get('bing_autosuggest', 0.0),
                zenrows_cost=cost_breakdown.get('zenrows', 0.0),
                llm_cost=cost_breakdown.get('llm', 0.0),
                total_cost=sum(cost_breakdown.values()),
                brave_searches=usage_counts.get('brave_searches', 0),
                bing_searches=usage_counts.get('bing_searches', 0),
                bing_autosuggest_calls=usage_counts.get('bing_autosuggest_calls', 0),
                zenrows_requests=usage_counts.get('zenrows_requests', 0),
                llm_tokens=usage_counts.get('llm_tokens', 0)
            )
            
            await self.session.commit()
            logger.info(f"Logged cost record for request: {search_request_id}")
            
        except Exception as e:
            logger.error(f"Failed to log cost record: {e}")
            await self.session.rollback()
            raise
    
    async def log_api_usage(
        self,
        provider: str,
        search_request_id: Optional[UUID] = None,
        endpoint: Optional[str] = None,
        method: str = "GET",
        response_status: Optional[int] = None,
        response_time: Optional[float] = None,
        success: bool = True,
        cost: float = 0.0,
        error_message: Optional[str] = None
    ):
        """Log API usage"""
        try:
            await self.api_repo.create_api_usage(
                provider=provider,
                search_request_id=search_request_id,
                endpoint=endpoint,
                method=method,
                response_status=response_status,
                response_time=response_time,
                success=success,
                cost=cost,
                error_message=error_message
            )
            
            await self.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to log API usage: {e}")
            # Don't rollback here as this might be called from other operations
    
    async def log_error(
        self,
        error_type: str,
        error_message: str,
        request_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
        stack_trace: Optional[str] = None,
        **context_data
    ):
        """Log application error"""
        try:
            await self.error_repo.log_error(
                error_type=error_type,
                error_message=error_message,
                request_id=request_id,
                user_id=user_id,
                stack_trace=stack_trace,
                context_data=context_data
            )
            
            await self.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
    
    async def mark_request_failed(
        self,
        request_id: str,
        error_message: str,
        error_type: str = "pipeline_error"
    ):
        """Mark a search request as failed"""
        try:
            await self.search_repo.update_search_request(
                request_id=request_id,
                status=RequestStatus.FAILED.value,
                error_message=error_message,
                completed_at=datetime.utcnow()
            )
            
            # Also log the error
            await self.log_error(
                error_type=error_type,
                error_message=error_message,
                request_id=request_id
            )
            
            await self.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to mark request as failed: {e}")
            await self.session.rollback()

# app/services/analytics_service.py
"""Analytics service for generating insights from stored data"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from app.database.repositories import (
    SearchRequestRepository, CostRecordRepository, ApiUsageRepository,
    StatsRepository, UserRepository
)

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Service for generating analytics and insights"""
    
    def __init__(self, session):
        self.session = session
        self.search_repo = SearchRequestRepository(session)
        self.cost_repo = CostRecordRepository(session)
        self.api_repo = ApiUsageRepository(session)
        self.stats_repo = StatsRepository(session)
        self.user_repo = UserRepository(session)
    
    async def get_dashboard_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get key metrics for dashboard"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get daily stats for the period
            daily_stats = await self.stats_repo.get_stats_range(start_date, end_date)
            
            # Calculate aggregated metrics
            total_requests = sum(stat.total_requests for stat in daily_stats)
            total_cost = sum(stat.total_cost for stat in daily_stats)
            avg_response_time = sum(stat.avg_response_time or 0 for stat in daily_stats) / len(daily_stats) if daily_stats else 0
            avg_cache_hit_rate = sum(stat.cache_hit_rate or 0 for stat in daily_stats) / len(daily_stats) if daily_stats else 0
            
            # Get recent error count
            recent_requests = await self.search_repo.get_recent_requests(hours=24)
            error_count = sum(1 for req in recent_requests if req.status == "failed")
            
            return {
                'period_days': days,
                'total_requests': total_requests,
                'total_cost': total_cost,
                'avg_response_time': avg_response_time,
                'cache_hit_rate': avg_cache_hit_rate,
                'error_rate': (error_count / len(recent_requests) * 100) if recent_requests else 0,
                'daily_breakdown': [
                    {
                        'date': stat.date.isoformat(),
                        'requests': stat.total_requests,
                        'cost': stat.total_cost,
                        'response_time': stat.avg_response_time,
                        'cache_hit_rate': stat.cache_hit_rate
                    }
                    for stat in daily_stats
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get dashboard metrics: {e}")
            return {}
    
    async def get_cost_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Get detailed cost analysis"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get cost breakdown by service
            daily_stats = await self.stats_repo.get_stats_range(start_date, end_date)
            
            total_costs = {
                'brave_search': sum(stat.brave_search_cost for stat in daily_stats),
                'bing_search': sum(stat.bing_search_cost for stat in daily_stats),
                'zenrows': sum(stat.zenrows_cost for stat in daily_stats),
                'total': sum(stat.total_cost for stat in daily_stats)
            }
            
            # Calculate cost per request
            total_requests = sum(stat.total_requests for stat in daily_stats)
            cost_per_request = total_costs['total'] / total_requests if total_requests > 0 else 0
            
            # Get top spending users (if tracking users)
            # This would require additional repository methods
            
            return {
                'period_days': days,
                'total_costs': total_costs,
                'cost_per_request': cost_per_request,
                'daily_costs': [
                    {
                        'date': stat.date.isoformat(),
                        'total': stat.total_cost,
                        'brave_search': stat.brave_search_cost,
                        'bing_search': stat.bing_search_cost,
                        'zenrows': stat.zenrows_cost
                    }
                    for stat in daily_stats
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to get cost analysis: {e}")
            return {}
    
    async def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics"""
        try:
            # Get recent requests
            recent_requests = await self.search_repo.get_recent_requests(hours=hours)
            
            if not recent_requests:
                return {'message': 'No recent requests found'}
            
            # Calculate performance metrics
            response_times = [req.processing_time for req in recent_requests if req.processing_time]
            cache_hits = sum(1 for req in recent_requests if req.cache_hit)
            successful_requests = sum(1 for req in recent_requests if req.status == "completed")
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            cache_hit_rate = (cache_hits / len(recent_requests)) * 100
            success_rate = (successful_requests / len(recent_requests)) * 100
            
            # Calculate percentiles
            sorted_times = sorted(response_times)
            p50 = sorted_times[len(sorted_times) // 2] if sorted_times else 0
            p95 = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0
            p99 = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0
            
            return {
                'period_hours': hours,
                'total_requests': len(recent_requests),
                'success_rate': success_rate,
                'cache_hit_rate': cache_hit_rate,
                'avg_response_time': avg_response_time,
                'response_time_percentiles': {
                    'p50': p50,
                    'p95': p95,
                    'p99': p99
                },
                'error_breakdown': {
                    'failed': sum(1 for req in recent_requests if req.status == "failed"),
                    'timeout': sum(1 for req in recent_requests if req.status == "timeout"),
                    'completed': successful_requests
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {}
    
    async def get_popular_queries(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most popular search queries"""
        try:
            # This would require a more complex query to group by query and count
            # For now, return recent unique queries
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            recent_requests = await self.search_repo.get_recent_requests(
                hours=days * 24, 
                limit=limit * 2
            )
            
            # Simple grouping by query (in production, this should be done in SQL)
            query_counts = {}
            for req in recent_requests:
                query = req.original_query.lower()
                if query in query_counts:
                    query_counts[query]['count'] += 1
                    query_counts[query]['avg_response_time'] = (
                        query_counts[query]['avg_response_time'] + (req.processing_time or 0)
                    ) / 2
                else:
                    query_counts[query] = {
                        'query': req.original_query,
                        'count': 1,
                        'avg_response_time': req.processing_time or 0,
                        'avg_confidence': req.confidence_score or 0
                    }
            
            # Sort by count and return top queries
            popular_queries = sorted(
                query_counts.values(), 
                key=lambda x: x['count'], 
                reverse=True
            )[:limit]
            
            return popular_queries
            
        except Exception as e:
            logger.error(f"Failed to get popular queries: {e}")
            return []

# Update app/api/dependencies.py to include database session
# Add this to the existing dependencies.py file

from app.database.connection import get_db_session
from app.services.database_logger import DatabaseLogger
from app.services.analytics_service import AnalyticsService

async def get_database_logger(session: AsyncSession = Depends(get_db_session)) -> DatabaseLogger:
    """Get database logger service"""
    return DatabaseLogger(session)

async def get_analytics_service(session: AsyncSession = Depends(get_db_session)) -> AnalyticsService:
    """Get analytics service"""
    return AnalyticsService(session)
