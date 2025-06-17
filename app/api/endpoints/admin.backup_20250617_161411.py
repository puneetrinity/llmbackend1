# app/api/endpoints/admin.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta

from app.database.connection import get_db_session
from app.services.analytics_service import AnalyticsService
from app.database.repositories import (
    UserRepository, SearchRequestRepository, ErrorRepository, 
    StatsRepository, CostRecordRepository
)
from app.api.dependencies import require_admin

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats/overview")
async def get_system_overview(
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """Get comprehensive system overview (admin only)"""
    try:
        analytics = AnalyticsService(db_session)
        
        # Get various time period metrics
        stats_24h = await analytics.get_dashboard_metrics(days=1)
        stats_7d = await analytics.get_dashboard_metrics(days=7)
        stats_30d = await analytics.get_dashboard_metrics(days=30)
        
        # Get performance metrics
        performance = await analytics.get_performance_metrics(hours=24)
        
        # Get cost analysis
        costs = await analytics.get_cost_analysis(days=30)
        
        # Get popular queries
        popular = await analytics.get_popular_queries(days=7, limit=10)
        
        return {
            "overview": {
                "last_24h": stats_24h,
                "last_7d": stats_7d,
                "last_30d": stats_30d
            },
            "performance": performance,
            "costs": costs,
            "popular_queries": popular,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system overview")

@router.get("/users")
async def list_users(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """List system users (admin only)"""
    try:
        user_repo = UserRepository(db_session)
        users = await user_repo.get_active_users(limit=limit + offset)
        
        # Apply offset manually (in production, do this in SQL)
        users = users[offset:offset + limit]
        
        user_list = []
        for user in users:
            user_list.append({
                "id": str(user.id),
                "identifier": user.user_identifier,
                "type": user.user_type,
                "is_active": user.is_active,
                "daily_request_limit": user.daily_request_limit,
                "monthly_cost_limit": user.monthly_cost_limit,
                "created_at": user.created_at.isoformat(),
                "last_request_at": user.last_request_at.isoformat() if user.last_request_at else None
            })
        
        return {
            "users": user_list,
            "total": len(user_list),
            "offset": offset,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Failed to list users")

@router.get("/users/{user_identifier}/details")
async def get_user_details(
    user_identifier: str,
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """Get detailed user information (admin only)"""
    try:
        user_repo = UserRepository(db_session)
        search_repo = SearchRequestRepository(db_session)
        cost_repo = CostRecordRepository(db_session)
        
        # Get user
        user = await user_repo.get_user_by_identifier(user_identifier)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user's recent requests
        recent_requests = await search_repo.get_user_requests(user.id, limit=20)
        
        # Get daily cost for today
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_cost = await cost_repo.get_user_daily_cost(user.id, today)
        
        # Format recent requests
        requests_data = []
        for req in recent_requests:
            requests_data.append({
                "request_id": req.request_id,
                "query": req.original_query[:100],  # Truncate for privacy
                "status": req.status,
                "processing_time": req.processing_time,
                "cost": req.total_cost,
                "created_at": req.created_at.isoformat()
            })
        
        return {
            "user": {
                "id": str(user.id),
                "identifier": user.user_identifier,
                "type": user.user_type,
                "is_active": user.is_active,
                "daily_request_limit": user.daily_request_limit,
                "monthly_cost_limit": user.monthly_cost_limit,
                "created_at": user.created_at.isoformat(),
                "last_request_at": user.last_request_at.isoformat() if user.last_request_at else None
            },
            "today_cost": daily_cost,
            "recent_requests": requests_data,
            "request_count": len(recent_requests)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user details")

@router.get("/requests")
async def list_requests(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    hours: int = Query(24, ge=1, le=168),  # Max 7 days
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """List search requests with filtering (admin only)"""
    try:
        search_repo = SearchRequestRepository(db_session)
        
        if status:
            from app.database.models import RequestStatus
            try:
                status_enum = RequestStatus(status)
                requests = await search_repo.get_requests_by_status(status_enum, limit=limit)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        else:
            requests = await search_repo.get_recent_requests(hours=hours, limit=limit)
        
        # Format requests
        requests_data = []
        for req in requests:
            requests_data.append({
                "request_id": req.request_id,
                "query": req.original_query[:100],  # Truncate
                "status": req.status,
                "user_id": str(req.user_id) if req.user_id else None,
                "processing_time": req.processing_time,
                "confidence_score": req.confidence_score,
                "cache_hit": req.cache_hit,
                "total_cost": req.total_cost,
                "created_at": req.created_at.isoformat(),
                "error_message": req.error_message[:200] if req.error_message else None
            })
        
        return {
            "requests": requests_data,
            "total": len(requests_data),
            "filters": {
                "status": status,
                "hours": hours,
                "limit": limit
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to list requests")

@router.get("/errors")
async def list_errors(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000),
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """List recent errors (admin only)"""
    try:
        error_repo = ErrorRepository(db_session)
        errors = await error_repo.get_recent_errors(hours=hours, limit=limit)
        
        errors_data = []
        for error in errors:
            errors_data.append({
                "id": str(error.id),
                "error_type": error.error_type,
                "error_message": error.error_message[:500],  # Truncate
                "request_id": error.request_id,
                "user_id": str(error.user_id) if error.user_id else None,
                "endpoint": error.endpoint,
                "created_at": error.created_at.isoformat(),
                "context_data": error.context_data
            })
        
        return {
            "errors": errors_data,
            "total": len(errors_data),
            "hours": hours,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error listing errors: {e}")
        raise HTTPException(status_code=500, detail="Failed to list errors")

@router.get("/costs/breakdown")
async def get_cost_breakdown(
    days: int = Query(30, ge=1, le=365),
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """Get detailed cost breakdown (admin only)"""
    try:
        cost_repo = CostRecordRepository(db_session)
        
        # Get daily cost breakdown for the period
        cost_data = []
        for day_offset in range(days):
            date = datetime.utcnow() - timedelta(days=day_offset)
            daily_breakdown = await cost_repo.get_daily_cost_breakdown(date)
            daily_breakdown["date"] = date.strftime("%Y-%m-%d")
            cost_data.append(daily_breakdown)
        
        # Calculate totals
        totals = {
            "brave_search": sum(day["brave_search"] for day in cost_data),
            "bing_search": sum(day["bing_search"] for day in cost_data),
            "zenrows": sum(day["zenrows"] for day in cost_data),
            "llm": sum(day["llm"] for day in cost_data),
            "total": sum(day["total"] for day in cost_data)
        }
        
        return {
            "period_days": days,
            "daily_breakdown": cost_data,
            "totals": totals,
            "average_daily_cost": totals["total"] / days if days > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting cost breakdown: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cost breakdown")

@router.get("/database/stats")
async def get_database_stats(
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """Get database statistics (admin only)"""
    try:
        # Get table sizes and record counts
        stats = {}
        
        # Count records in each main table
        table_queries = {
            "users": "SELECT COUNT(*) FROM users",
            "search_requests": "SELECT COUNT(*) FROM search_requests",
            "content_sources": "SELECT COUNT(*) FROM content_sources", 
            "cost_records": "SELECT COUNT(*) FROM cost_records",
            "api_usage": "SELECT COUNT(*) FROM api_usage",
            "cache_entries": "SELECT COUNT(*) FROM cache_entries",
            "error_logs": "SELECT COUNT(*) FROM error_logs"
        }
        
        for table_name, query in table_queries.items():
            try:
                result = await db_session.execute(query)
                count = result.scalar()
                stats[table_name] = count
            except Exception as e:
                stats[table_name] = f"Error: {str(e)}"
        
        # Get recent activity
        recent_activity = {
            "requests_last_24h": await db_session.execute(
                "SELECT COUNT(*) FROM search_requests WHERE created_at > NOW() - INTERVAL '24 hours'"
            ),
            "errors_last_24h": await db_session.execute(
                "SELECT COUNT(*) FROM error_logs WHERE created_at > NOW() - INTERVAL '24 hours'"
            )
        }
        
        for key, result in recent_activity.items():
            recent_activity[key] = result.scalar()
        
        return {
            "table_counts": stats,
            "recent_activity": recent_activity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get database statistics")

@router.post("/database/cleanup")
async def cleanup_database(
    days: int = Query(30, ge=1, le=365, description="Delete records older than X days"),
    dry_run: bool = Query(True, description="Preview what would be deleted"),
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """Cleanup old database records (admin only)"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        cleanup_queries = {
            "old_cache_entries": f"DELETE FROM cache_entries WHERE created_at < '{cutoff_date}'",
            "old_error_logs": f"DELETE FROM error_logs WHERE created_at < '{cutoff_date}'",
            "old_api_usage": f"DELETE FROM api_usage WHERE created_at < '{cutoff_date}'",
            # Be more conservative with search requests - they contain valuable data
            "very_old_search_requests": f"DELETE FROM search_requests WHERE created_at < '{cutoff_date - timedelta(days=30)}'"
        }
        
        if dry_run:
            # Count what would be deleted
            preview = {}
            for operation, query in cleanup_queries.items():
                count_query = query.replace("DELETE", "SELECT COUNT(*)").split(" WHERE")[0] + " WHERE" + query.split(" WHERE")[1]
                try:
                    result = await db_session.execute(count_query)
                    preview[operation] = result.scalar()
                except Exception as e:
                    preview[operation] = f"Error: {str(e)}"
            
            return {
                "dry_run": True,
                "cutoff_date": cutoff_date.isoformat(),
                "preview": preview,
                "message": "This is a preview. Set dry_run=false to execute cleanup."
            }
        
        else:
            # Execute cleanup
            deleted_counts = {}
            for operation, query in cleanup_queries.items():
                try:
                    result = await db_session.execute(query)
                    deleted_counts[operation] = result.rowcount
                except Exception as e:
                    deleted_counts[operation] = f"Error: {str(e)}"
            
            await db_session.commit()
            
            return {
                "dry_run": False,
                "cutoff_date": cutoff_date.isoformat(),
                "deleted_counts": deleted_counts,
                "message": "Cleanup completed successfully."
            }
        
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail="Failed to cleanup database")

@router.post("/cache/clear")
async def clear_system_cache(
    cache_type: Optional[str] = Query(None, description="Specific cache type to clear"),
    _: None = Depends(require_admin)
):
    """Clear system cache (admin only)"""
    try:
        from app.services.cache_service import CacheService
        cache = CacheService()
        
        await cache.clear_cache(pattern=cache_type)
        
        return {
            "message": "Cache cleared successfully",
            "cache_type": cache_type or "all",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

@router.get("/monitoring/health")
async def get_detailed_health(
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_admin)
):
    """Get detailed system health information (admin only)"""
    try:
        from app.core.pipeline import SearchPipeline
        
        # Get pipeline health
        pipeline = SearchPipeline()
        health_status = await pipeline.health_check()
        
        # Get database-specific health metrics
        db_health = {
            "connection": "healthy",
            "recent_errors": 0,
            "recent_requests": 0
        }
        
        try:
            # Count recent errors
            error_result = await db_session.execute(
                "SELECT COUNT(*) FROM error_logs WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            db_health["recent_errors"] = error_result.scalar()
            
            # Count recent requests
            request_result = await db_session.execute(
                "SELECT COUNT(*) FROM search_requests WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            db_health["recent_requests"] = request_result.scalar()
            
        except Exception as e:
            db_health["connection"] = "unhealthy"
            db_health["error"] = str(e)
        
        return {
            "pipeline": health_status,
            "database": db_health,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting detailed health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health information")
