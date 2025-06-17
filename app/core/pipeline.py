# app/core/pipeline.py
import asyncio
import time
import logging
from typing import Dict, List, Optional
from uuid import uuid4

from app.services.query_enhancer import QueryEnhancementService
from app.services.search_engine import MultiSearchEngine
from app.services.content_fetcher import ZenRowsContentFetcher
from app.services.llm_analyzer import LLMAnalysisService
from app.services.cache_service import CacheService
from app.models.responses import SearchResponse
from app.core.exceptions import PipelineException

logger = logging.getLogger(__name__)

# Simple cost tracker stub
class SimpleCostTracker:
    async def start_request(self, request_id: str, user_id: Optional[str] = None):
        logger.debug(f"Cost tracking started for {request_id}")
        
    async def end_request(self, request_id: str):
        logger.debug(f"Cost tracking ended for {request_id}")
        
    async def handle_error(self, request_id: str, error: Exception):
        logger.debug(f"Cost tracking error for {request_id}: {error}")

class SearchPipeline:
    def __init__(self):
        self.query_enhancer = QueryEnhancementService()
        self.search_engine = MultiSearchEngine()
        self.content_fetcher = ZenRowsContentFetcher()
        self.llm_analyzer = LLMAnalysisService()
        self.cache = CacheService()
        self.cost_tracker = SimpleCostTracker()  # Simple implementation
        
        # Pipeline state
        self.is_healthy = True
        self.last_health_check = 0
    
    async def process_query(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        max_results: int = 8
    ) -> SearchResponse:
        """Main pipeline processing method"""
        request_id = str(uuid4())
        start_time = time.time()
        
        logger.info(f"Starting pipeline for query: {query[:50]}...", 
                   extra={"request_id": request_id})
        
        try:
            # Track request start
            await self.cost_tracker.start_request(request_id, user_id)
            
            # Stage 1: Check cache
            try:
                cached_response = await self.cache.get_response(query)
                if cached_response:
                    logger.info(f"Cache hit for query", extra={"request_id": request_id})
                    if hasattr(cached_response, 'cached'):
                        cached_response.cached = True
                    return cached_response
            except Exception as e:
                logger.warning(f"Cache get failed: {e}")
            
            # Stage 2: Query enhancement
            logger.info("Starting query enhancement", extra={"request_id": request_id})
            try:
                enhanced_queries = await self.query_enhancer.enhance(query)
            except Exception as e:
                logger.warning(f"Query enhancement failed: {e}, using original query")
                enhanced_queries = [query]
            
            # Stage 3: Parallel search
            logger.info("Starting parallel search", extra={"request_id": request_id})
            try:
                search_results = await self.search_engine.search_multiple(
                    enhanced_queries, max_results_per_query=max_results
                )
            except Exception as e:
                logger.error(f"Search failed: {e}")
                search_results = []
            
            # Stage 4: Content fetching
            logger.info("Starting content fetching", extra={"request_id": request_id})
            try:
                content_data = await self.content_fetcher.fetch_content(
                    search_results, max_urls=max_results
                )
            except Exception as e:
                logger.error(f"Content fetch failed: {e}")
                content_data = []
            
            # Stage 5: LLM analysis
            logger.info("Starting LLM analysis", extra={"request_id": request_id})
            try:
                final_response = await self.llm_analyzer.analyze(
                    query, content_data, request_id
                )
            except Exception as e:
                logger.error(f"LLM analysis failed: {e}, creating fallback response")
                # Create fallback response
                sources = [result.url for result in search_results[:3]] if search_results else []
                final_response = SearchResponse(
                    query=query,
                    answer=f"I found {len(search_results)} search results for '{query}', but analysis is currently unavailable.",
                    sources=sources,
                    confidence=0.3,
                    processing_time=0.0,
                    cached=False
                )
            
            # Add processing metadata
            processing_time = time.time() - start_time
            final_response.processing_time = processing_time
            final_response.cached = False
            
            # Stage 6: Cache response
            try:
                await self.cache.store_response(query, final_response)
            except Exception as e:
                logger.warning(f"Cache store failed: {e}")
            
            logger.info(f"Pipeline completed in {processing_time:.2f}s", 
                       extra={"request_id": request_id})
            
            return final_response
            
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}", 
                        extra={"request_id": request_id}, exc_info=True)
            await self.cost_tracker.handle_error(request_id, e)
            raise PipelineException(f"Pipeline processing failed: {str(e)}")
        
        finally:
            await self.cost_tracker.end_request(request_id)
    
    async def health_check(self) -> Dict[str, str]:
        """Check health of all pipeline components"""
        checks = {}
        
        # Check each component safely
        for component_name, component in [
            ("query_enhancer", self.query_enhancer),
            ("search_engine", self.search_engine),
            ("content_fetcher", self.content_fetcher),
            ("llm_analyzer", self.llm_analyzer),
            ("cache", self.cache)
        ]:
            try:
                if hasattr(component, 'health_check'):
                    checks[component_name] = await component.health_check()
                else:
                    checks[component_name] = "healthy"  # Assume healthy if no health check
            except Exception as e:
                logger.warning(f"Health check failed for {component_name}: {e}")
                checks[component_name] = "unhealthy"
        
        overall_status = "healthy" if all(
            status == "healthy" for status in checks.values()
        ) else "degraded"
        
        return {"overall": overall_status, **checks}
