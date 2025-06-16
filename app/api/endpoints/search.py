# app/api/endpoints/search.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import Optional
from uuid import UUID

from app.core.pipeline import SearchPipeline
from app.models.requests import SearchRequest
from app.models.responses import SearchResponse, ErrorResponse
from app.api.dependencies import get_pipeline, get_current_user, rate_limit
from app.core.exceptions import PipelineException, RateLimitException
from app.database.connection import get_db_session
from app.services.database_logger import DatabaseLogger
from app.services.analytics_service import AnalyticsService
from app.database.models import RequestStatus

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post(
    "/search",
    response_model=SearchResponse,
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    },
    summary="Search and analyze content",
    description="Process a search query and return AI-generated response with sources. All requests are logged to database for analytics."
)
async def search_query(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    pipeline: SearchPipeline = Depends(get_pipeline),
    current_user: Optional[str] = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    _: None = Depends(rate_limit)
):
    """
    Process a search query and return intelligent, sourced results.
    
    - **query**: The search query (1-500 characters)
    - **max_results**: Maximum number of sources to include (1-20)
    - **include_sources**: Whether to include source URLs in response
    
    All search requests are logged to the database for analytics and monitoring.
    """
    db_logger = DatabaseLogger(db_session)
    search_request_id = None
    
    try:
        # Validate max_results doesn't exceed system limits
        max_allowed = 20
        if request.max_results > max_allowed:
            raise HTTPException(
                status_code=400, 
                detail=f"max_results cannot exceed {max_allowed}"
            )
        
        # Get client information
        client_ip = getattr(request, 'client', {}).get('host') if hasattr(request, 'client') else None
        user_agent = getattr(request, 'headers', {}).get('user-agent') if hasattr(request, 'headers') else None
        
        # Log search request to database
        search_request_id = await db_logger.log_search_request(
            request_id=getattr(request, 'state', {}).get('request_id', 'unknown'),
            user_identifier=current_user,
            original_query=request.query,
            max_results=request.max_results,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        # Process the query through pipeline
        response = await pipeline.process_query(
            query=request.query,
            user_id=current_user,
            max_results=request.max_results
        )
        
        # Filter sources if requested
        if not request.include_sources:
            response.sources = []
        
        # Update database with response
        await db_logger.update_search_response(
            request_id=getattr(request, 'state', {}).get('request_id', 'unknown'),
            response=response,
            status=RequestStatus.COMPLETED
        )
        
        # Log analytics in background
        background_tasks.add_task(
            log_search_analytics,
            search_request_id=search_request_id,
            response=response,
            user_id=current_user,
            db_session=db_session
        )
        
        return response
        
    except PipelineException as e:
        # Log failed request to database
        if search_request_id:
            await db_logger.mark_request_failed(
                request_id=getattr(request, 'state', {}).get('request_id', 'unknown'),
                error_message=str(e),
                error_type="pipeline_error"
            )
        
        logger.error(f"Pipeline error for query '{request.query}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    except Exception as e:
        # Log unexpected error to database
        if search_request_id:
            await db_logger.mark_request_failed(
                request_id=getattr(request, 'state', {}).get('request_id', 'unknown'),
                error_message=str(e),
                error_type="unexpected_error"
            )
        
        logger.error(f"Unexpected error for query '{request.query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/search/suggestions")
async def get_search_suggestions(
    q: str,
    pipeline: SearchPipeline = Depends(get_pipeline),
    current_user: Optional[str] = Depends(get_current_user),
    _: None = Depends(rate_limit)
):
    """Get search query suggestions"""
    try:
        if len(q.strip()) < 2:
            return {"suggestions": []}
        
        suggestions = await pipeline.query_enhancer.get_suggestions_only(q)
        return {"suggestions": suggestions}
        
    except Exception as e:
        logger.error(f"Error getting suggestions: {str(e)}")
        return {"suggestions": []}

@router.get("/search/stats")
async def get_search_stats(
    pipeline: SearchPipeline = Depends(get_pipeline),
    db_session: AsyncSession = Depends(get_db_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Get search pipeline statistics from database"""
    try:
        analytics = AnalyticsService(db_session)
        
        # Get various metrics
        dashboard_metrics = await analytics.get_dashboard_metrics(days=7)
        performance_metrics = await analytics.get_performance_metrics(hours=24)
        cost_analysis = await analytics.get_cost_analysis(days=30)
        
        # Combine with pipeline stats
        pipeline_stats = await pipeline.get_pipeline_stats()
        
        return {
            "pipeline": pipeline_stats,
            "dashboard": dashboard_metrics,
            "performance": performance_metrics,
            "costs": cost_analysis,
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
    except Exception as e:
        logger.error(f"Error getting search stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@router.get("/search/analytics/dashboard")
async def get_dashboard_analytics(
    days: int = 7,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Get dashboard analytics data"""
    try:
        analytics = AnalyticsService(db_session)
        dashboard_data = await analytics.get_dashboard_metrics(days=days)
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error getting dashboard analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard data")

@router.get("/search/analytics/costs")
async def get_cost_analytics(
    days: int = 30,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Get cost analytics data"""
    try:
        analytics = AnalyticsService(db_session)
        cost_data = await analytics.get_cost_analysis(days=days)
        return cost_data
        
    except Exception as e:
        logger.error(f"Error getting cost analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get cost data")

@router.get("/search/analytics/performance")
async def get_performance_analytics(
    hours: int = 24,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Get performance analytics data"""
    try:
        analytics = AnalyticsService(db_session)
        performance_data = await analytics.get_performance_metrics(hours=hours)
        return performance_data
        
    except Exception as e:
        logger.error(f"Error getting performance analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get performance data")

@router.get("/search/analytics/popular-queries")
async def get_popular_queries(
    days: int = 7,
    limit: int = 10,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Get most popular search queries"""
    try:
        analytics = AnalyticsService(db_session)
        popular_queries = await analytics.get_popular_queries(days=days, limit=limit)
        return {"queries": popular_queries}
        
    except Exception as e:
        logger.error(f"Error getting popular queries: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get popular queries")

@router.get("/search/history")
async def get_search_history(
    limit: int = 50,
    offset: int = 0,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Get user's search history (if authenticated)"""
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        from app.database.repositories import UserRepository, SearchRequestRepository
        
        user_repo = UserRepository(db_session)
        search_repo = SearchRequestRepository(db_session)
        
        # Get user
        user = await user_repo.get_user_by_identifier(current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user's search requests
        requests = await search_repo.get_user_requests(user.id, limit=limit, offset=offset)
        
        # Format response
        history = []
        for req in requests:
            history.append({
                "request_id": req.request_id,
                "query": req.original_query,
                "status": req.status,
                "confidence_score": req.confidence_score,
                "processing_time": req.processing_time,
                "cache_hit": req.cache_hit,
                "cost": req.total_cost,
                "created_at": req.created_at.isoformat(),
                "sources_count": len(req.response_sources) if req.response_sources else 0
            })
        
        return {
            "history": history,
            "total": len(history),
            "offset": offset,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting search history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get search history")

@router.get("/search/request/{request_id}")
async def get_search_request_details(
    request_id: str,
    db_session: AsyncSession = Depends(get_db_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Get detailed information about a specific search request"""
    try:
        from app.database.repositories import SearchRequestRepository
        
        search_repo = SearchRequestRepository(db_session)
        request = await search_repo.get_search_request_by_id(request_id)
        
        if not request:
            raise HTTPException(status_code=404, detail="Search request not found")
        
        # Format detailed response
        return {
            "request": {
                "id": request.request_id,
                "query": request.original_query,
                "enhanced_queries": request.enhanced_queries,
                "status": request.status,
                "answer": request.response_answer,
                "sources": request.response_sources,
                "confidence_score": request.confidence_score,
                "processing_time": request.processing_time,
                "cache_hit": request.cache_hit,
                "total_cost": request.total_cost,
                "created_at": request.created_at.isoformat(),
                "completed_at": request.completed_at.isoformat() if request.completed_at else None,
                "error_message": request.error_message
            },
            "content_sources": [
                {
                    "url": source.url,
                    "title": source.title,
                    "word_count": source.word_count,
                    "source_type": source.source_type,
                    "confidence_score": source.confidence_score,
                    "fetch_successful": source.fetch_successful
                }
                for source in request.content_sources
            ],
            "cost_breakdown": [
                {
                    "brave_search": cost.brave_search_cost,
                    "bing_search": cost.bing_search_cost,
                    "zenrows": cost.zenrows_cost,
                    "llm": cost.llm_cost,
                    "total": cost.total_cost
                }
                for cost in request.cost_records
            ],
            "api_usage": [
                {
                    "provider": usage.provider,
                    "response_time": usage.response_time,
                    "success": usage.success,
                    "cost": usage.cost
                }
                for usage in request.api_usage_records
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting request details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get request details")

@router.post("/search/clear-cache")
async def clear_search_cache(
    pattern: Optional[str] = None,
    pipeline: SearchPipeline = Depends(get_pipeline),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Clear search cache (admin function)"""
    try:
        # In a real app, you'd want admin authentication here
        await pipeline.clear_cache(pattern)
        return {"message": f"Cache cleared successfully", "pattern": pattern}
        
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

@router.get("/search/cost/{request_id}")
async def get_request_cost(
    request_id: str,
    pipeline: SearchPipeline = Depends(get_pipeline),
    current_user: Optional[str] = Depends(get_current_user)
):
    """Get cost breakdown for a specific request"""
    try:
        cost_data = await pipeline.cost_tracker.get_request_cost(request_id)
        
        if not cost_data:
            raise HTTPException(status_code=404, detail="Request not found")
        
        return cost_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting request cost: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get cost data")

async def log_search_analytics(
    search_request_id: UUID,
    response: SearchResponse,
    user_id: Optional[str],
    db_session: AsyncSession
):
    """Background task to log additional analytics data"""
    try:
        db_logger = DatabaseLogger(db_session)
        
        # Log any additional analytics here
        # This could include user behavior tracking, A/B test data, etc.
        
        logger.info(f"Analytics logged for request: {search_request_id}")
        
    except Exception as e:
        logger.error(f"Error logging analytics: {e}")

async def log_search_request(
    query: str, 
    user_id: Optional[str], 
    response_time: float, 
    cached: bool,
    cost: Optional[float]
):
    """Background task to log search requests (legacy function - now handled by DatabaseLogger)"""
    try:
        # This function is kept for backward compatibility
        # The actual logging is now handled by DatabaseLogger during the request
        log_data = {
            "query": query[:100],  # Truncate for privacy
            "user_id": user_id,
            "response_time": response_time,
            "cached": cached,
            "cost": cost,
            "timestamp": "now"
        }
        
        logger.info(f"Search logged: {log_data}")
        
    except Exception as e:
        logger.error(f"Error logging search request: {e}")
