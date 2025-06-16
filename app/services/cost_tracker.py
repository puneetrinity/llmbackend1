# app/services/cost_tracker.py - Fixed with optional database imports
import logging
import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json
from uuid import UUID

from app.config.settings import settings
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

# Optional database imports - graceful degradation if not available
try:
    from app.database.connection import db_manager
    from app.database.repositories import CostRecordRepository, UserRepository, ApiUsageRepository
    DATABASE_AVAILABLE = True
    logger.info("✅ Database modules loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️ Database modules not available: {e}. Running with cache-only cost tracking.")
    db_manager = None
    CostRecordRepository = None
    UserRepository = None
    ApiUsageRepository = None
    DATABASE_AVAILABLE = False

@dataclass
class RequestCost:
    request_id: str
    user_id: Optional[str]
    start_time: float
    end_time: Optional[float] = None
    brave_searches: int = 0
    serpapi_searches: int = 0  # Replaced bing_searches and bing_autosuggest_calls
    zenrows_requests: int = 0
    llm_tokens: int = 0
    total_cost: float = 0.0
    status: str = "active"  # active, completed, error
    search_request_db_id: Optional[UUID] = None  # Database ID

class DatabaseCostTracker:
    """Enhanced cost tracker with database integration and SerpApi support"""
    
    def __init__(self):
        self.cache = CacheService()
        self.active_requests: Dict[str, RequestCost] = {}
        
        # Updated cost rates (USD)
        self.cost_rates = {
            "brave_search": 0.005,          # $0.005 per search
            "serpapi_search": 0.02,         # $0.02 per search (typical SerpApi rate)
            "zenrows_request": 0.01,        # $0.01 per request
            "llm_token": 0.0,               # Ollama is free (local)
        }
        
        # Daily budget tracking
        self.daily_budget = settings.DAILY_BUDGET_USD
        self.monthly_zenrows_budget = settings.ZENROWS_MONTHLY_BUDGET
        self.monthly_serpapi_budget = settings.SERPAPI_MONTHLY_BUDGET
    
    async def start_request(self, request_id: str, user_id: Optional[str] = None, 
                          search_request_db_id: Optional[UUID] = None):
        """Start tracking a new request"""
        try:
            request_cost = RequestCost(
                request_id=request_id,
                user_id=user_id,
                start_time=time.time(),
                search_request_db_id=search_request_db_id
            )
            
            self.active_requests[request_id] = request_cost
            logger.info(f"💰 Started cost tracking for request: {request_id}")
            
        except Exception as e:
            logger.error(f"Error starting cost tracking: {e}")
    
    async def track_brave_search(self, request_id: str, num_searches: int = 1):
        """Track Brave search API usage"""
        try:
            if request_id in self.active_requests:
                self.active_requests[request_id].brave_searches += num_searches
                cost = num_searches * self.cost_rates["brave_search"]
                self.active_requests[request_id].total_cost += cost
                
                # Log to database if available
                if DATABASE_AVAILABLE:
                    await self._log_api_usage(
                        request_id=request_id,
                        provider="brave_search",
                        cost=cost,
                        calls=num_searches
                    )
                
                logger.debug(f"💰 Tracked {num_searches} Brave searches for {request_id}: +${cost:.4f}")
            
        except Exception as e:
            logger.error(f"Error tracking Brave search cost: {e}")
    
    async def track_serpapi_search(self, request_id: str, num_searches: int = 1):
        """Track SerpApi search usage"""
        try:
            if request_id in self.active_requests:
                self.active_requests[request_id].serpapi_searches += num_searches
                cost = num_searches * self.cost_rates["serpapi_search"]
                self.active_requests[request_id].total_cost += cost
                
                # Log to database if available
                if DATABASE_AVAILABLE:
                    await self._log_api_usage(
                        request_id=request_id,
                        provider="serpapi",
                        cost=cost,
                        calls=num_searches
                    )
                
                logger.debug(f"💰 Tracked {num_searches} SerpApi searches for {request_id}: +${cost:.4f}")
            
        except Exception as e:
            logger.error(f"Error tracking SerpApi search cost: {e}")
    
    async def track_zenrows_request(self, request_id: str, num_requests: int = 1):
        """Track ZenRows API usage"""
        try:
            if request_id in self.active_requests:
                self.active_requests[request_id].zenrows_requests += num_requests
                cost = num_requests * self.cost_rates["zenrows_request"]
                self.active_requests[request_id].total_cost += cost
                
                # Log to database if available
                if DATABASE_AVAILABLE:
                    await self._log_api_usage(
                        request_id=request_id,
                        provider="zenrows",
                        cost=cost,
                        calls=num_requests
                    )
                
                logger.debug(f"💰 Tracked {num_requests} ZenRows requests for {request_id}: +${cost:.4f}")
            
        except Exception as e:
            logger.error(f"Error tracking ZenRows cost: {e}")
    
    async def track_llm_usage(self, request_id: str, token_count: int):
        """Track LLM token usage"""
        try:
            if request_id in self.active_requests:
                self.active_requests[request_id].llm_tokens += token_count
                cost = token_count * self.cost_rates["llm_token"]
                self.active_requests[request_id].total_cost += cost
                
                # Log to database if available (even if cost is 0 for tracking purposes)
                if DATABASE_AVAILABLE:
                    await self._log_api_usage(
                        request_id=request_id,
                        provider="ollama",
                        cost=cost,
                        tokens=token_count
                    )
                
                logger.debug(f"💰 Tracked {token_count} LLM tokens for {request_id}: +${cost:.6f}")
            
        except Exception as e:
            logger.error(f"Error tracking LLM cost: {e}")
    
    async def end_request(self, request_id: str) -> Optional[RequestCost]:
        """End request tracking and return final cost"""
        try:
            if request_id in self.active_requests:
                request_cost = self.active_requests[request_id]
                request_cost.end_time = time.time()
                request_cost.status = "completed"
                
                # Store cost record in database if available
                if DATABASE_AVAILABLE:
                    await self._store_cost_record(request_cost)
                    await self._update_daily_totals(request_cost)
                
                # Always store in cache for tracking
                await self._store_request_cost(request_cost)
                
                # Remove from active requests
                del self.active_requests[request_id]
                
                duration = request_cost.end_time - request_cost.start_time
                logger.info(f"💰 Request {request_id} completed in {duration:.2f}s - Total cost: ${request_cost.total_cost:.4f}")
                
                return request_cost
            
            return None
            
        except Exception as e:
            logger.error(f"Error ending cost tracking: {e}")
            return None
    
    async def handle_error(self, request_id: str, error: Exception):
        """Handle error in request processing"""
        try:
            if request_id in self.active_requests:
                request_cost = self.active_requests[request_id]
                request_cost.end_time = time.time()
                request_cost.status = "error"
                
                # Store error cost record in database if available
                if DATABASE_AVAILABLE:
                    await self._store_cost_record(request_cost)
                    await self._update_daily_totals(request_cost)
                
                # Store error request for tracking in cache
                await self._store_request_cost(request_cost)
                
                # Remove from active requests
                del self.active_requests[request_id]
                
                logger.warning(f"⚠️ Request {request_id} errored - Partial cost: ${request_cost.total_cost:.4f}")
            
        except Exception as e:
            logger.error(f"Error handling request error: {e}")
    
    async def _log_api_usage(self, request_id: str, provider: str, cost: float, 
                           calls: int = 1, tokens: Optional[int] = None):
        """Log API usage to database (if available)"""
        if not DATABASE_AVAILABLE or not db_manager:
            return
        
        try:
            request_cost = self.active_requests.get(request_id)
            if not request_cost:
                return
            
            async with db_manager.get_session() as session:
                api_repo = ApiUsageRepository(session)
                
                await api_repo.create_api_usage(
                    provider=provider,
                    search_request_id=request_cost.search_request_db_id,
                    cost=cost,
                    success=True,
                    tokens_used=tokens
                )
                
                await session.commit()
            
        except Exception as e:
            logger.error(f"Error logging API usage to database: {e}")
    
    async def _store_cost_record(self, request_cost: RequestCost):
        """Store cost record in database (if available)"""
        if not DATABASE_AVAILABLE or not db_manager:
            return
        
        try:
            if not request_cost.search_request_db_id:
                return
            
            async with db_manager.get_session() as session:
                cost_repo = CostRecordRepository(session)
                user_repo = UserRepository(session)
                
                # Get user ID if available
                user_db_id = None
                if request_cost.user_id:
                    user = await user_repo.get_user_by_identifier(request_cost.user_id)
                    if user:
                        user_db_id = user.id
                
                # Create cost record with updated fields
                await cost_repo.create_cost_record(
                    search_request_id=request_cost.search_request_db_id,
                    user_id=user_db_id,
                    brave_search_cost=request_cost.brave_searches * self.cost_rates["brave_search"],
                    bing_search_cost=request_cost.serpapi_searches * self.cost_rates["serpapi_search"],  # Store SerpApi cost here temporarily
                    bing_autosuggest_cost=0.0,
                    zenrows_cost=request_cost.zenrows_requests * self.cost_rates["zenrows_request"],
                    llm_cost=request_cost.llm_tokens * self.cost_rates["llm_token"],
                    total_cost=request_cost.total_cost,
                    brave_searches=request_cost.brave_searches,
                    bing_searches=request_cost.serpapi_searches,  # Store SerpApi searches here temporarily
                    bing_autosuggest_calls=0,
                    zenrows_requests=request_cost.zenrows_requests,
                    llm_tokens=request_cost.llm_tokens
                )
                
                await session.commit()
                logger.debug(f"💾 Stored cost record in database for request: {request_cost.request_id}")
            
        except Exception as e:
            logger.error(f"Error storing cost record in database: {e}")
    
    async def _store_request_cost(self, request_cost: RequestCost):
        """Store request cost data for historical tracking in cache"""
        try:
            # Store individual request in cache
            cache_key = f"cost:request:{request_cost.request_id}"
            await self.cache.set(cache_key, asdict(request_cost), ttl=86400)  # 24 hour retention
            
        except Exception as e:
            logger.error(f"Error storing request cost in cache: {e}")
    
    async def _update_daily_totals(self, request_cost: RequestCost):
        """Update daily cost totals in database (if available)"""
        if not DATABASE_AVAILABLE or not db_manager:
            return
        
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with db_manager.get_session() as session:
                from app.database.repositories import StatsRepository
                stats_repo = StatsRepository(session)
                
                # Get existing daily stats
                daily_stats = await stats_repo.get_daily_stats(today)
                
                if daily_stats:
                    # Update existing stats
                    await stats_repo.create_or_update_daily_stats(
                        date=today,
                        total_cost=daily_stats.total_cost + request_cost.total_cost,
                        brave_search_cost=daily_stats.brave_search_cost + (request_cost.brave_searches * self.cost_rates["brave_search"]),
                        bing_search_cost=daily_stats.bing_search_cost + (request_cost.serpapi_searches * self.cost_rates["serpapi_search"]),  # Store SerpApi cost here
                        zenrows_cost=daily_stats.zenrows_cost + (request_cost.zenrows_requests * self.cost_rates["zenrows_request"]),
                        total_api_calls=daily_stats.total_api_calls + (
                            request_cost.brave_searches + request_cost.serpapi_searches + request_cost.zenrows_requests
                        ),
                        total_llm_tokens=daily_stats.total_llm_tokens + request_cost.llm_tokens
                    )
                else:
                    # Create new daily stats
                    await stats_repo.create_or_update_daily_stats(
                        date=today,
                        total_cost=request_cost.total_cost,
                        brave_search_cost=request_cost.brave_searches * self.cost_rates["brave_search"],
                        bing_search_cost=request_cost.serpapi_searches * self.cost_rates["serpapi_search"],  # Store SerpApi cost here
                        zenrows_cost=request_cost.zenrows_requests * self.cost_rates["zenrows_request"],
                        total_api_calls=(
                            request_cost.brave_searches + request_cost.serpapi_searches + request_cost.zenrows_requests
                        ),
                        total_llm_tokens=request_cost.llm_tokens
                    )
                
                await session.commit()
            
            # Check budget alerts
            await self._check_budget_alerts()
            
        except Exception as e:
            logger.error(f"Error updating daily totals in database: {e}")
    
    async def _check_budget_alerts(self):
        """Check if we're approaching budget limits"""
        try:
            daily_stats = await self.get_daily_stats()
            daily_cost = daily_stats.get("total_cost", 0)
            
            # Daily budget check
            if daily_cost > self.daily_budget * 0.8:  # 80% threshold
                logger.warning(f"⚠️ Daily budget alert: ${daily_cost:.2f} / ${self.daily_budget:.2f} (80% threshold)")
            
            if daily_cost > self.daily_budget:
                logger.error(f"🚨 Daily budget exceeded: ${daily_cost:.2f} / ${self.daily_budget:.2f}")
            
        except Exception as e:
            logger.error(f"Error checking budget alerts: {e}")
    
    async def get_daily_stats(self, date: Optional[str] = None) -> Dict:
        """Get daily cost statistics"""
        try:
            if not DATABASE_AVAILABLE or not db_manager:
                # Fallback to cache-based stats
                return await self._get_daily_stats_from_cache(date)
            
            if not date:
                target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                target_date = datetime.fromisoformat(date).replace(hour=0, minute=0, second=0, microsecond=0)
            
            async with db_manager.get_session() as session:
                from app.database.repositories import StatsRepository
                stats_repo = StatsRepository(session)
                
                daily_stats = await stats_repo.get_daily_stats(target_date)
                
                if not daily_stats:
                    return {
                        "date": target_date.isoformat(),
                        "total_cost": 0.0,
                        "request_count": 0,
                        "brave_searches": 0,
                        "serpapi_searches": 0,
                        "zenrows_requests": 0,
                        "llm_tokens": 0,
                        "budget_utilization": 0.0
                    }
                
                return {
                    "date": daily_stats.date.isoformat(),
                    "total_cost": daily_stats.total_cost,
                    "request_count": daily_stats.total_requests,
                    "brave_search_cost": daily_stats.brave_search_cost,
                    "serpapi_search_cost": daily_stats.bing_search_cost,  # SerpApi cost stored in bing field
                    "zenrows_cost": daily_stats.zenrows_cost,
                    "total_api_calls": daily_stats.total_api_calls,
                    "total_llm_tokens": daily_stats.total_llm_tokens,
                    "budget_utilization": (daily_stats.total_cost / self.daily_budget) * 100
                }
            
        except Exception as e:
            logger.error(f"Error getting daily stats from database: {e}")
            return await self._get_daily_stats_from_cache(date)
    
    async def _get_daily_stats_from_cache(self, date: Optional[str] = None) -> Dict:
        """Get daily stats from cache (fallback when database unavailable)"""
        try:
            if not date:
                date_str = datetime.utcnow().date().isoformat()
            else:
                date_str = date
            
            cache_key = f"daily_stats:{date_str}"
            cached_stats = await self.cache.get(cache_key)
            
            if cached_stats:
                return cached_stats
            else:
                return {
                    "date": date_str,
                    "total_cost": 0.0,
                    "request_count": 0,
                    "brave_searches": 0,
                    "serpapi_searches": 0,
                    "zenrows_requests": 0,
                    "llm_tokens": 0,
                    "budget_utilization": 0.0,
                    "source": "cache_fallback"
                }
                
        except Exception as e:
            logger.error(f"Error getting daily stats from cache: {e}")
            return {"error": str(e)}
    
    async def get_request_cost(self, request_id: str) -> Optional[Dict]:
        """Get cost data for a specific request"""
        try:
            # Check active requests first
            if request_id in self.active_requests:
                return asdict(self.active_requests[request_id])
            
            # Check cached completed requests
            cache_key = f"cost:request:{request_id}"
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                return cached_data
            
            # Check database if available
            if DATABASE_AVAILABLE and db_manager:
                try:
                    async with db_manager.get_session() as session:
                        from app.database.repositories import SearchRequestRepository
                        search_repo = SearchRequestRepository(session)
                        
                        request = await search_repo.get_search_request_by_id(request_id)
                        if request and request.cost_records:
                            cost_record = request.cost_records[0]  # Get first cost record
                            return {
                                "request_id": request_id,
                                "total_cost": cost_record.total_cost,
                                "brave_search_cost": cost_record.brave_search_cost,
                                "serpapi_search_cost": cost_record.bing_search_cost,  # SerpApi cost stored in bing field
                                "zenrows_cost": cost_record.zenrows_cost,
                                "llm_cost": cost_record.llm_cost,
                                "brave_searches": cost_record.brave_searches,
                                "serpapi_searches": cost_record.bing_searches,  # SerpApi searches stored in bing field
                                "zenrows_requests": cost_record.zenrows_requests,
                                "llm_tokens": cost_record.llm_tokens
                            }
                except Exception as e:
                    logger.error(f"Error querying database for request cost: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting request cost: {e}")
            return None
    
    async def is_budget_available(self) -> bool:
        """Check if daily budget allows more requests"""
        try:
            daily_stats = await self.get_daily_stats()
            return daily_stats.get("total_cost", 0) < self.daily_budget
            
        except Exception as e:
            logger.error(f"Error checking budget availability: {e}")
            return True  # Fail open
    
    async def get_cost_breakdown(self) -> Dict:
        """Get cost breakdown by service"""
        try:
            daily_stats = await self.get_daily_stats()
            
            breakdown = {
                "brave_search": daily_stats.get("brave_search_cost", 0),
                "serpapi_search": daily_stats.get("serpapi_search_cost", 0),  # Updated field name
                "zenrows": daily_stats.get("zenrows_cost", 0),
                "llm": 0.0,  # Ollama is free
                "total": daily_stats.get("total_cost", 0),
                "database_available": DATABASE_AVAILABLE
            }
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error getting cost breakdown: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> str:
        """Health check for cost tracker"""
        try:
            # Test basic functionality
            test_request_id = "health_check_test"
            await self.start_request(test_request_id, "test_user")
            await self.track_brave_search(test_request_id, 1)
            result = await self.end_request(test_request_id)
            
            if result and result.total_cost > 0:
                return "healthy"
            else:
                return "degraded"
                
        except Exception as e:
            logger.error(f"Cost tracker health check failed: {e}")
            return "unhealthy"

# Keep backward compatibility
CostTracker = DatabaseCostTracker
