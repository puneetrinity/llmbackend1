# app/api/endpoints/search.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import logging
from typing import Optional

from app.core.pipeline import SearchPipeline
from app.models.requests import SearchRequest
from app.models.responses import SearchResponse, ErrorResponse
from app.api.dependencies import get_pipeline, get_current_user, rate_limit
from app.core.exceptions import PipelineException

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
    description="Process a search query and return AI-generated response with sources."
)
async def search_query(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    pipeline: SearchPipeline = Depends(get_pipeline),
    current_user: Optional[str] = Depends(get_current_user),
    _: None = Depends(rate_limit)
):
    """
    Process a search query and return intelligent, sourced results.
    
    - **query**: The search query (1-500 characters)
    - **max_results**: Maximum number of sources to include (1-20) 
    - **include_sources**: Whether to include source URLs in response
    """
    try:
        # Process the query through pipeline
        response = await pipeline.process_query(
            query=request.query,
            user_id=current_user,
            max_results=request.max_results
        )
        
        # Log successful request in background
        background_tasks.add_task(
            log_search_request,
            query=request.query,
            user_id=current_user,
            response_time=response.processing_time,
            cached=response.cached
        )
        
        return response
        
    except PipelineException as e:
        logger.error(f"Pipeline error for query '{request.query}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error for query '{request.query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/search/suggestions")
async def get_search_suggestions(
    q: str,
    pipeline: SearchPipeline = Depends(get_pipeline)
):
    """Get search query suggestions"""
    try:
        suggestions = await pipeline.query_enhancer.get_suggestions_only(q)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error getting suggestions: {str(e)}")
        return {"suggestions": []}

async def log_search_request(
    query: str, 
    user_id: Optional[str], 
    response_time: float, 
    cached: bool
):
    """Background task to log search requests"""
    logger.info(
        f"Search completed - Query: '{query[:50]}...', "
        f"User: {user_id}, Time: {response_time:.2f}s, Cached: {cached}"
    )
