# app/api/endpoints/health.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import time
import logging
from typing import Dict

from app.core.pipeline import SearchPipeline
from app.models.responses import HealthResponse
from app.api.dependencies import get_pipeline
from app.database.connection import get_db_session
from app.services.analytics_service import AnalyticsService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint"""
    return HealthResponse(
        status="healthy",
        services={"api": "healthy"},
        response_time_ms=0.0
    )

@router.get("/detailed", response_model=HealthResponse)
async def detailed_health_check(
    pipeline: SearchPipeline = Depends(get_pipeline),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Detailed health check of all pipeline components including database"""
    start_time = time.time()
    
    try:
        # Check all pipeline components (includes database check)
        health_status = await pipeline.health_check()
        
        # Add additional database-specific checks
        db_details = await _check_database_details(db_session)
        health_status.update(db_details)
        
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Determine overall status
        overall_status = health_status.get("overall", "unknown")
        
        return HealthResponse(
            status=overall_status,
            services=health_status,
            response_time_ms=round(response_time, 2)
        )
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        response_time = (time.time() - start_time) * 1000
        
        return HealthResponse(
            status="unhealthy",
            services={"error": str(e)},
            response_time_ms=round(response_time, 2)
        )

@router.get("/ready")
async def readiness_check(
    pipeline: SearchPipeline = Depends(get_pipeline),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Kubernetes readiness probe endpoint"""
    try:
        # Quick check if essential services are ready
        health_status = await pipeline.health_check()
        
        # Essential services that must be healthy for readiness
        essential_services = ["cache", "search_engine", "database"]
        ready = all(
            health_status.get(service, "unhealthy") in ["healthy", "degraded"]
            for service in essential_services
        )
        
        # Additional database readiness check
        if ready:
            try:
                await db_session.execute("SELECT 1")
                db_ready = True
            except Exception as e:
                logger.warning(f"Database not ready: {e}")
                db_ready = False
                ready = False
        
        if ready:
            return {"status": "ready", "database": "ready" if db_ready else "not_ready"}
        else:
            raise HTTPException(status_code=503, detail="Service not ready")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check error: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint"""
    try:
        # Simple check that the application is running
        return {"status": "alive", "timestamp": time.time()}
        
    except Exception as e:
        logger.error(f"Liveness check error: {e}")
        raise HTTPException(status_code=500, detail="Service not alive")

@router.get("/database")
async def database_health_check(
    db_session: AsyncSession = Depends(get_db_session)
):
    """Specific database health check endpoint"""
    start_time = time.time()
    
    try:
        # Test basic connectivity
        await db_session.execute("SELECT 1")
        
        # Test table access
        table_checks = {}
        essential_tables = [
            "users", "search_requests", "content_sources", 
            "cost_records", "api_usage", "daily_stats"
        ]
        
        for table in essential_tables:
            try:
                result = await db_session.execute(f"SELECT COUNT(*) FROM {table} LIMIT 1")
                count = result.scalar()
                table_checks[table] = {"status": "accessible", "record_count": count}
            except Exception as e:
                table_checks[table] = {"status": "error", "error": str(e)}
        
        # Get recent activity
        recent_activity = await _get_recent_database_activity(db_session)
        
        response_time = (time.time() - start_time) * 1000
        
        # Determine overall database health
        unhealthy_tables = [
            table for table, status in table_checks.items() 
            if status.get("status") != "accessible"
        ]
        
        overall_status = "healthy" if not unhealthy_tables else "degraded"
        
        return {
            "status": overall_status,
            "response_time_ms": round(response_time, 2),
            "tables": table_checks,
            "recent_activity": recent_activity,
            "issues": unhealthy_tables if unhealthy_tables else None
        }
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Database health check failed: {e}")
        
        return {
            "status": "unhealthy",
            "response_time_ms": round(response_time, 2),
            "error": str(e)
        }

@router.get("/metrics")
async def get_metrics(
    pipeline: SearchPipeline = Depends(get_pipeline),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get comprehensive metrics for monitoring"""
    try:
        # Get pipeline stats
        pipeline_stats = await pipeline.get_pipeline_stats()
        
        # Get database metrics
        analytics = AnalyticsService(db_session)
        performance_metrics = await analytics.get_performance_metrics(hours=1)
        dashboard_metrics = await analytics.get_dashboard_metrics(days=1)
        
        # Get database-specific metrics
        db_metrics = await _get_database_metrics(db_session)
        
        # System metrics
        system_metrics = {
            "uptime_seconds": time.time(),  # Simplified uptime
            "python_info": {
                "version": "3.11+",
                "implementation": "CPython"
            }
        }
        
        # Combine all metrics
        metrics = {
            "pipeline": pipeline_stats,
            "performance": performance_metrics,
            "dashboard": dashboard_metrics,
            "database": db_metrics,
            "system": system_metrics,
            "timestamp": time.time()
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics")

@router.get("/status")
async def get_overall_status(
    pipeline: SearchPipeline = Depends(get_pipeline),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get overall system status summary"""
    try:
        # Get health status
        health_status = await pipeline.health_check()
        
        # Get recent error rate
        analytics = AnalyticsService(db_session)
        performance = await analytics.get_performance_metrics(hours=1)
        
        # Calculate overall system health score
        healthy_components = sum(
            1 for status in health_status.values() 
            if status == "healthy"
        )
        total_components = len(health_status) - 1  # Exclude 'overall' key
        health_score = (healthy_components / total_components * 100) if total_components > 0 else 0
        
        # Determine status color/level
        if health_score >= 90:
            status_level = "excellent"
            color = "green"
        elif health_score >= 75:
            status_level = "good"
            color = "yellow"
        elif health_score >= 50:
            status_level = "degraded"
            color = "orange"
        else:
            status_level = "critical"
            color = "red"
        
        return {
            "overall_status": health_status.get("overall", "unknown"),
            "health_score": round(health_score, 1),
            "status_level": status_level,
            "color": color,
            "success_rate": performance.get("success_rate", 0),
            "avg_response_time": performance.get("avg_response_time", 0),
            "total_requests_1h": performance.get("total_requests", 0),
            "components": {
                name: status for name, status in health_status.items() 
                if name != "overall"
            },
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        return {
            "overall_status": "error",
            "health_score": 0,
            "status_level": "critical",
            "color": "red",
            "error": str(e),
            "timestamp": time.time()
        }

async def _check_database_details(db_session: AsyncSession) -> Dict:
    """Get detailed database health information"""
    try:
        db_details = {
            "database_connection": "healthy",
            "database_recent_errors": 0,
            "database_recent_requests": 0
        }
        
        # Count recent errors
        try:
            error_result = await db_session.execute(
                "SELECT COUNT(*) FROM error_logs WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            db_details["database_recent_errors"] = error_result.scalar()
        except Exception:
            db_details["database_recent_errors"] = "unknown"
        
        # Count recent requests
        try:
            request_result = await db_session.execute(
                "SELECT COUNT(*) FROM search_requests WHERE created_at > NOW() - INTERVAL '1 hour'"
            )
            db_details["database_recent_requests"] = request_result.scalar()
        except Exception:
            db_details["database_recent_requests"] = "unknown"
        
        return db_details
        
    except Exception as e:
        return {
            "database_connection": "unhealthy",
            "database_error": str(e)
        }

async def _get_recent_database_activity(db_session: AsyncSession) -> Dict:
    """Get recent database activity metrics"""
    try:
        activity = {}
        
        # Recent requests (last hour)
        result = await db_session.execute(
            "SELECT COUNT(*) FROM search_requests WHERE created_at > NOW() - INTERVAL '1 hour'"
        )
        activity["requests_last_hour"] = result.scalar()
        
        # Recent errors (last hour)
        result = await db_session.execute(
            "SELECT COUNT(*) FROM error_logs WHERE created_at > NOW() - INTERVAL '1 hour'"
        )
        activity["errors_last_hour"] = result.scalar()
        
        # Recent users (last 24 hours)
        result = await db_session.execute(
            "SELECT COUNT(DISTINCT user_id) FROM search_requests WHERE created_at > NOW() - INTERVAL '24 hours' AND user_id IS NOT NULL"
        )
        activity["unique_users_last_24h"] = result.scalar()
        
        return activity
        
    except Exception as e:
        return {"error": str(e)}

async def _get_database_metrics(db_session: AsyncSession) -> Dict:
    """Get database-specific metrics"""
    try:
        metrics = {}
        
        # Table sizes
        table_sizes = {}
        tables = ["users", "search_requests", "content_sources", "cost_records", "api_usage"]
        
        for table in tables:
            try:
                result = await db_session.execute(f"SELECT COUNT(*) FROM {table}")
                table_sizes[table] = result.scalar()
            except Exception:
                table_sizes[table] = "error"
        
        metrics["table_sizes"] = table_sizes
        
        # Recent activity metrics
        metrics["recent_activity"] = await _get_recent_database_activity(db_session)
        
        return metrics
        
    except Exception as e:
        return {"error": str(e)}
