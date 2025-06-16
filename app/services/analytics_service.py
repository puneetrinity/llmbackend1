# app/services/analytics_service.py - Complete analytics service
import logging
import json
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from uuid import UUID
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class InteractionType(Enum):
    """Enumeration of interaction types"""
    SEARCH = "search"
    VIEW = "view"
    CLICK = "click"
    DOWNLOAD = "download"
    SHARE = "share"
    FEEDBACK = "feedback"
    ERROR = "error"

@dataclass
class AnalyticsConfig:
    """Configuration for analytics service"""
    enabled: bool = True
    max_cache_days: int = 7
    max_cache_size: int = 10000
    track_user_data: bool = True
    track_performance: bool = True
    track_errors: bool = True
    batch_size: int = 100
    flush_interval: int = 300  # seconds

@dataclass
class SearchEvent:
    """Search event data structure"""
    query: str
    user_id: Optional[str]
    source: str
    timestamp: str
    metadata: Dict[str, Any]
    session_id: Optional[str] = None

@dataclass
class PerformanceEvent:
    """Performance event data structure"""
    query: str
    result_count: int
    processing_time: float
    success: bool
    error_type: Optional[str]
    timestamp: str
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None

class AnalyticsService:
    """Complete analytics service for tracking usage and performance"""
    
    def __init__(self, config: Optional[AnalyticsConfig] = None):
        self.config = config or AnalyticsConfig()
        self.enabled = self.config.enabled
        self.analytics_cache = {}
        self.performance_cache = {}
        self.interaction_cache = {}
        self.error_cache = {}
        self.session_cache = {}
        self._last_cleanup = datetime.utcnow()
        self._batch_queue = []
        
        logger.info("📊 Analytics service initialized")
        
        # Start background tasks if enabled
        if self.enabled:
            asyncio.create_task(self._periodic_cleanup())
            asyncio.create_task(self._periodic_flush())
    
    async def track_search_query(
        self,
        query: str,
        user_id: Optional[str] = None,
        source: str = "api",
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ):
        """Track search query for analytics"""
        if not self.enabled:
            return
            
        try:
            search_event = SearchEvent(
                query=query[:100],  # Truncate for privacy
                user_id=user_id,
                source=source,
                timestamp=datetime.utcnow().isoformat(),
                metadata=metadata or {},
                session_id=session_id
            )
            
            # Store in memory cache
            today = datetime.utcnow().date().isoformat()
            if today not in self.analytics_cache:
                self.analytics_cache[today] = []
            
            self.analytics_cache[today].append(asdict(search_event))
            
            # Track session data
            if session_id:
                await self._track_session_activity(session_id, "search", query)
            
            logger.debug(f"📊 Tracked search query: {query[:30]}... from {source}")
            
            # Check cache size limits
            await self._check_cache_limits()
            
        except Exception as e:
            logger.error(f"Error tracking search query: {e}")
            await self.track_error("search_tracking", str(e))
    
    async def track_search_result(
        self,
        query: str,
        result_count: int,
        processing_time: float,
        success: bool = True,
        error_type: Optional[str] = None,
        memory_usage: Optional[float] = None,
        cpu_usage: Optional[float] = None
    ):
        """Track search result performance"""
        if not self.enabled or not self.config.track_performance:
            return
            
        try:
            perf_event = PerformanceEvent(
                query=query[:100],
                result_count=result_count,
                processing_time=processing_time,
                success=success,
                error_type=error_type,
                timestamp=datetime.utcnow().isoformat(),
                memory_usage=memory_usage,
                cpu_usage=cpu_usage
            )
            
            # Store performance metrics
            today = datetime.utcnow().date().isoformat()
            perf_key = f"performance_{today}"
            if perf_key not in self.performance_cache:
                self.performance_cache[perf_key] = []
            
            self.performance_cache[perf_key].append(asdict(perf_event))
            
            logger.debug(f"📊 Tracked search result: {result_count} results in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error tracking search result: {e}")
            await self.track_error("performance_tracking", str(e))
    
    async def track_user_interaction(
        self,
        user_id: Optional[str],
        interaction_type: Union[str, InteractionType],
        data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ):
        """Track user interactions"""
        if not self.enabled:
            return
            
        try:
            if isinstance(interaction_type, InteractionType):
                interaction_type = interaction_type.value
                
            interaction_data = {
                "user_id": user_id,
                "interaction_type": interaction_type,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id
            }
            
            # Store interaction data
            today = datetime.utcnow().date().isoformat()
            interaction_key = f"interactions_{today}"
            if interaction_key not in self.interaction_cache:
                self.interaction_cache[interaction_key] = []
            
            self.interaction_cache[interaction_key].append(interaction_data)
            
            # Track session data
            if session_id:
                await self._track_session_activity(session_id, interaction_type, data)
            
            logger.debug(f"📊 Tracked user interaction: {interaction_type}")
            
        except Exception as e:
            logger.error(f"Error tracking user interaction: {e}")
            await self.track_error("interaction_tracking", str(e))
    
    async def track_error(
        self,
        error_type: str,
        error_message: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Track errors for monitoring"""
        if not self.enabled or not self.config.track_errors:
            return
            
        try:
            error_data = {
                "error_type": error_type,
                "error_message": error_message[:500],  # Truncate long messages
                "user_id": user_id,
                "context": context or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            today = datetime.utcnow().date().isoformat()
            error_key = f"errors_{today}"
            if error_key not in self.error_cache:
                self.error_cache[error_key] = []
            
            self.error_cache[error_key].append(error_data)
            
            logger.debug(f"📊 Tracked error: {error_type}")
            
        except Exception as e:
            logger.error(f"Error tracking error: {e}")
    
    async def get_search_analytics(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive search analytics data"""
        try:
            if not start_date:
                start_date = datetime.utcnow().date().isoformat()
            if not end_date:
                end_date = start_date
            
            analytics_data = {
                "date_range": {"start": start_date, "end": end_date},
                "total_searches": 0,
                "successful_searches": 0,
                "average_processing_time": 0.0,
                "popular_queries": [],
                "error_rate": 0.0,
                "unique_users": 0,
                "search_sources": {},
                "hourly_distribution": {},
                "query_length_stats": {}
            }
            
            # Collect data for date range
            current_date = datetime.fromisoformat(start_date).date()
            end_date_obj = datetime.fromisoformat(end_date).date()
            
            all_searches = []
            all_performance = []
            
            while current_date <= end_date_obj:
                date_str = current_date.isoformat()
                
                # Get search data
                search_data = self.analytics_cache.get(date_str, [])
                all_searches.extend(search_data)
                
                # Get performance data
                perf_data = self.performance_cache.get(f"performance_{date_str}", [])
                all_performance.extend(perf_data)
                
                current_date += timedelta(days=1)
            
            # Calculate metrics
            if all_searches:
                analytics_data["total_searches"] = len(all_searches)
                
                # Unique users
                unique_users = set(s.get("user_id") for s in all_searches if s.get("user_id"))
                analytics_data["unique_users"] = len(unique_users)
                
                # Popular queries
                query_counts = Counter(s.get("query", "") for s in all_searches)
                analytics_data["popular_queries"] = [
                    {"query": q, "count": c} for q, c in query_counts.most_common(10)
                ]
                
                # Search sources
                source_counts = Counter(s.get("source", "unknown") for s in all_searches)
                analytics_data["search_sources"] = dict(source_counts)
                
                # Hourly distribution
                hourly_counts = defaultdict(int)
                for search in all_searches:
                    try:
                        hour = datetime.fromisoformat(search["timestamp"]).hour
                        hourly_counts[hour] += 1
                    except:
                        continue
                analytics_data["hourly_distribution"] = dict(hourly_counts)
                
                # Query length statistics
                query_lengths = [len(s.get("query", "")) for s in all_searches]
                if query_lengths:
                    analytics_data["query_length_stats"] = {
                        "average": sum(query_lengths) / len(query_lengths),
                        "min": min(query_lengths),
                        "max": max(query_lengths)
                    }
            
            if all_performance:
                successful = [p for p in all_performance if p.get("success", True)]
                analytics_data["successful_searches"] = len(successful)
                
                if successful:
                    avg_time = sum(p.get("processing_time", 0) for p in successful) / len(successful)
                    analytics_data["average_processing_time"] = round(avg_time, 2)
                
                if len(all_performance) > 0:
                    error_rate = (len(all_performance) - len(successful)) / len(all_performance) * 100
                    analytics_data["error_rate"] = round(error_rate, 2)
            
            return analytics_data
            
        except Exception as e:
            logger.error(f"Error getting search analytics: {e}")
            return {"error": str(e)}
    
    async def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get detailed performance metrics"""
        try:
            # Get recent performance data
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            recent_performance = []
            for perf_list in self.performance_cache.values():
                for perf in perf_list:
                    try:
                        perf_time = datetime.fromisoformat(perf["timestamp"])
                        if perf_time >= cutoff_time:
                            recent_performance.append(perf)
                    except:
                        continue
            
            if not recent_performance:
                return {
                    "total_requests": 0,
                    "average_response_time": 0.0,
                    "success_rate": 100.0,
                    "requests_per_hour": 0.0,
                    "p95_response_time": 0.0,
                    "p99_response_time": 0.0
                }
            
            total_requests = len(recent_performance)
            successful_requests = len([p for p in recent_performance if p.get("success", True)])
            
            # Response time statistics
            response_times = [p.get("processing_time", 0) for p in recent_performance if p.get("success", True)]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # Percentiles
            response_times.sort()
            p95_response_time = response_times[int(len(response_times) * 0.95)] if response_times else 0
            p99_response_time = response_times[int(len(response_times) * 0.99)] if response_times else 0
            
            success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 100.0
            requests_per_hour = total_requests / hours
            
            return {
                "total_requests": total_requests,
                "average_response_time": round(avg_response_time, 2),
                "success_rate": round(success_rate, 2),
                "requests_per_hour": round(requests_per_hour, 2),
                "p95_response_time": round(p95_response_time, 2),
                "p99_response_time": round(p99_response_time, 2),
                "time_window_hours": hours
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {"error": str(e)}
    
    async def get_usage_statistics(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics"""
        try:
            today = datetime.utcnow().date().isoformat()
            search_data = self.analytics_cache.get(today, [])
            interaction_data = self.interaction_cache.get(f"interactions_{today}", [])
            error_data = self.error_cache.get(f"errors_{today}", [])
            
            # Count unique users
            unique_users = set()
            for data in search_data:
                if data.get("user_id"):
                    unique_users.add(data["user_id"])
            
            # Interaction type breakdown
            interaction_types = Counter(i.get("interaction_type", "unknown") for i in interaction_data)
            
            # Error type breakdown
            error_types = Counter(e.get("error_type", "unknown") for e in error_data)
            
            return {
                "total_searches_today": len(search_data),
                "unique_users_today": len(unique_users),
                "total_interactions_today": len(interaction_data),
                "total_errors_today": len(error_data),
                "interaction_breakdown": dict(interaction_types),
                "error_breakdown": dict(error_types),
                "cache_stats": {
                    "analytics_cache_size": len(self.analytics_cache),
                    "performance_cache_size": len(self.performance_cache),
                    "interaction_cache_size": len(self.interaction_cache),
                    "error_cache_size": len(self.error_cache),
                    "session_cache_size": len(self.session_cache)
                },
                "total_data_points": sum(
                    len(v) if isinstance(v, list) else 1 
                    for cache in [self.analytics_cache, self.performance_cache, 
                                self.interaction_cache, self.error_cache]
                    for v in cache.values()
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting usage statistics: {e}")
            return {"error": str(e)}
    
    async def get_user_analytics(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get analytics for a specific user"""
        try:
            user_searches = []
            user_interactions = []
            
            # Collect user data from recent days
            for i in range(days):
                date = (datetime.utcnow().date() - timedelta(days=i)).isoformat()
                
                # Search data
                searches = self.analytics_cache.get(date, [])
                user_searches.extend([s for s in searches if s.get("user_id") == user_id])
                
                # Interaction data
                interactions = self.interaction_cache.get(f"interactions_{date}", [])
                user_interactions.extend([i for i in interactions if i.get("user_id") == user_id])
            
            # Calculate user-specific metrics
            query_counts = Counter(s.get("query", "") for s in user_searches)
            interaction_counts = Counter(i.get("interaction_type", "") for i in user_interactions)
            
            return {
                "user_id": user_id,
                "date_range_days": days,
                "total_searches": len(user_searches),
                "total_interactions": len(user_interactions),
                "favorite_queries": [{"query": q, "count": c} for q, c in query_counts.most_common(5)],
                "interaction_breakdown": dict(interaction_counts),
                "search_sources": dict(Counter(s.get("source", "") for s in user_searches)),
                "active_days": len(set(s["timestamp"][:10] for s in user_searches))
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {"error": str(e)}
    
    async def get_trend_analysis(self, days: int = 7) -> Dict[str, Any]:
        """Get trend analysis over time"""
        try:
            daily_stats = {}
            
            for i in range(days):
                date = (datetime.utcnow().date() - timedelta(days=i)).isoformat()
                
                searches = self.analytics_cache.get(date, [])
                performance = self.performance_cache.get(f"performance_{date}", [])
                
                daily_stats[date] = {
                    "searches": len(searches),
                    "unique_users": len(set(s.get("user_id") for s in searches if s.get("user_id"))),
                    "avg_processing_time": 0.0,
                    "success_rate": 100.0
                }
                
                if performance:
                    successful = [p for p in performance if p.get("success", True)]
                    if successful:
                        avg_time = sum(p.get("processing_time", 0) for p in successful) / len(successful)
                        daily_stats[date]["avg_processing_time"] = round(avg_time, 2)
                    
                    if len(performance) > 0:
                        success_rate = len(successful) / len(performance) * 100
                        daily_stats[date]["success_rate"] = round(success_rate, 2)
            
            return {
                "days_analyzed": days,
                "daily_breakdown": daily_stats,
                "trends": {
                    "search_trend": self._calculate_trend([stats["searches"] for stats in daily_stats.values()]),
                    "user_trend": self._calculate_trend([stats["unique_users"] for stats in daily_stats.values()]),
                    "performance_trend": self._calculate_trend([stats["avg_processing_time"] for stats in daily_stats.values()])
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting trend analysis: {e}")
            return {"error": str(e)}
    
    async def export_analytics(
        self,
        start_date: str,
        end_date: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """Export analytics data"""
        try:
            export_data = {
                "export_info": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "format": format,
                    "exported_at": datetime.utcnow().isoformat()
                },
                "analytics": await self.get_search_analytics(start_date, end_date),
                "performance": await self.get_performance_metrics(hours=24),
                "usage": await self.get_usage_statistics()
            }
            
            if format == "json":
                return export_data
            else:
                return {"error": f"Unsupported format: {format}"}
                
        except Exception as e:
            logger.error(f"Error exporting analytics: {e}")
            return {"error": str(e)}
    
    async def clear_old_data(self, days_to_keep: int = None):
        """Clear old analytics data to prevent memory buildup"""
        if days_to_keep is None:
            days_to_keep = self.config.max_cache_days
            
        try:
            cutoff_date = datetime.utcnow().date() - timedelta(days=days_to_keep)
            
            caches_to_clean = [
                self.analytics_cache,
                self.performance_cache,
                self.interaction_cache,
                self.error_cache
            ]
            
            total_removed = 0
            
            for cache in caches_to_clean:
                keys_to_remove = []
                for key in cache.keys():
                    try:
                        # Extract date from key
                        if '_' in key:
                            date_str = key.split('_')[-1]
                        else:
                            date_str = key
                        
                        key_date = datetime.fromisoformat(date_str).date()
                        if key_date < cutoff_date:
                            keys_to_remove.append(key)
                    except:
                        continue
                
                for key in keys_to_remove:
                    del cache[key]
                    total_removed += 1
            
            if total_removed > 0:
                logger.info(f"📊 Cleared {total_removed} old analytics entries")
            
        except Exception as e:
            logger.error(f"Error clearing old analytics data: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for analytics service"""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {}
            }
            
            # Test basic functionality
            test_start = datetime.utcnow()
            await self.track_search_query("health_check_test", "test_user", "health_check")
            await self.track_search_result("health_check_test", 1, 0.1, True)
            test_duration = (datetime.utcnow() - test_start).total_seconds()
            
            health_status["checks"]["tracking_functionality"] = {
                "status": "pass",
                "duration_ms": round(test_duration * 1000, 2)
            }
            
            # Check cache sizes
            total_cache_size = sum(
                len(cache) for cache in [
                    self.analytics_cache,
                    self.performance_cache,
                    self.interaction_cache,
                    self.error_cache
                ]
            )
            
            cache_status = "pass" if total_cache_size < self.config.max_cache_size else "warn"
            health_status["checks"]["cache_size"] = {
                "status": cache_status,
                "current_size": total_cache_size,
                "max_size": self.config.max_cache_size
            }
            
            # Check if service is enabled
            health_status["checks"]["service_enabled"] = {
                "status": "pass" if self.enabled else "warn",
                "enabled": self.enabled
            }
            
            # Overall status
            if any(check["status"] == "fail" for check in health_status["checks"].values()):
                health_status["status"] = "unhealthy"
            elif any(check["status"] == "warn" for check in health_status["checks"].values()):
                health_status["status"] = "degraded"
            
            return health_status
                
        except Exception as e:
            logger.error(f"Analytics service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    # Private helper methods
    
    async def _track_session_activity(self, session_id: str, activity_type: str, data: Any):
        """Track session-level activity"""
        if session_id not in self.session_cache:
            self.session_cache[session_id] = {
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
                "activities": []
            }
        
        self.session_cache[session_id]["last_activity"] = datetime.utcnow().isoformat()
        self.session_cache[session_id]["activities"].append({
            "type": activity_type,
            "data": str(data)[:100],  # Truncate for privacy
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _check_cache_limits(self):
        """Check and enforce cache size limits"""
        total_size = sum(
            len(cache) for cache in [
                self.analytics_cache,
                self.performance_cache,
                self.interaction_cache,
                self.error_cache
            ]
        )
        
        if total_size > self.config.max_cache_size:
            await self.clear_old_data(days_to_keep=self.config.max_cache_days // 2)
    
    async def _periodic_cleanup(self):
        """Periodic cleanup task"""
        while self.enabled:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self.clear_old_data()
                
                # Clean old sessions
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                old_sessions = [
                    sid for sid, data in self.session_cache.items()
                    if datetime.fromisoformat(data["last_activity"]) < cutoff_time
                ]
                
                for sid in old_sessions:
                    del self.session_cache[sid]
                
                if old_sessions:
                    logger.info(f"📊 Cleaned {len(old_sessions)} old sessions")
                    
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def _periodic_flush(self):
        """Periodic flush task for batch processing"""
        while self.enabled:
            try:
                await asyncio.sleep(self.config.flush_interval)
                
                if self._batch_queue:
                    logger.info(f"📊 Flushing {len(self._batch_queue)} batched events")
                    self._batch_queue.clear()
                    
            except Exception as e:
                logger.error(f"Error in periodic flush: {e}")
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from a list of values"""
        if len(values) < 2:
            return "insufficient_data"
        
        # Simple trend calculation
        recent_avg = sum(values[:len(values)//2]) / (len(values)//2)
        older_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
        
        if recent_avg > older_avg * 1.1:
            return "increasing"
        elif recent_avg < older_avg * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def __del__(self):
        """Cleanup when service is destroyed"""
        try:
            if hasattr(self, 'enabled') and self.enabled:
                logger.info("📊 Analytics service shutting down")
        except:
            pass
