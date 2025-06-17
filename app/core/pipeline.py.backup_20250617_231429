from sqlalchemy import text
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
from app.services.cost_tracker import DatabaseCostTracker
from app.services.database_logger import DatabaseLogger
from app.models.responses import SearchResponse
from app.core.exceptions import PipelineException
from app.database.connection import db_manager
from app.database.models import RequestStatus

logger = logging.getLogger(__name__)

class SearchPipeline:
    def __init__(self):
        self.query_enhancer = QueryEnhancementService()
        self.search_engine = MultiSearchEngine()
        self.content_fetcher = ZenRowsContentFetcher()
        self.llm_analyzer = LLMAnalysisService()
        self.cache = CacheService()
        self.cost_tracker = DatabaseCostTracker()

        # Pipeline state
        self.is_healthy = True
        self.last_health_check = 0

    async def process_query(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        max_results: int = 8
    ) -> SearchResponse:
        request_id = str(uuid4())
        start_time = time.time()
        db_logger = None
        search_request_db_id = None

        logger.info(f"Starting pipeline for query: {query[:50]}...", 
                   extra={"request_id": request_id})

        try:
            if not await self.cost_tracker.is_budget_available():
                logger.warning(f"Daily budget exceeded, rejecting request: {request_id}")
                raise PipelineException("Daily budget exceeded. Please try again tomorrow.")

            async with db_manager.get_session_context() as db_session:
                db_logger = DatabaseLogger(db_session)
                search_request_db_id = await db_logger.log_search_request(
                    request_id=request_id,
                    user_identifier=user_id,
                    original_query=query,
                    max_results=max_results
                )

                await self.cost_tracker.start_request(
                    request_id, 
                    user_id, 
                    search_request_db_id=search_request_db_id
                )

                # ✅ FIXED: use standalone function get_response()
                try:
                    cached_response = await get_response(query)
                except Exception as e:
                    logger.warning(f"Cache lookup failed: {e}")
                    cached_response = None

                if cached_response:
                    logger.info(f"Cache hit for query", extra={"request_id": request_id})
                    cached_response.cached = True

                    await db_logger.update_search_response(
                        request_id=request_id,
                        response=cached_response,
                        status=RequestStatus.COMPLETED
                    )

                    await self.cost_tracker.end_request(request_id)
                    return cached_response

                logger.info("Starting query enhancement", extra={"request_id": request_id})
                enhanced_queries = await self._run_with_timeout(
                    self.query_enhancer.enhance(query),
                    timeout=5.0,
                    stage_name="query_enhancement"
                )

                logger.info("Starting parallel search", extra={"request_id": request_id})
                search_results = await self._run_with_timeout(
                    self.search_engine.search_multiple(enhanced_queries, max_results_per_query=max_results),
                    timeout=15.0,
                    stage_name="search"
                )

                search_count = len(enhanced_queries) if enhanced_queries else 1
                await self.cost_tracker.track_brave_search(request_id, search_count)
                await self.cost_tracker.track_serpapi_search(request_id, search_count)

                logger.info("Starting content fetching", extra={"request_id": request_id})
                content_data = await self._run_with_timeout(
                    self.content_fetcher.fetch_content(search_results, max_urls=max_results),
                    timeout=20.0,
                    stage_name="content_fetch"
                )

                zenrows_requests = len([c for c in content_data if c.fetch_time > 0])
                if zenrows_requests > 0:
                    await self.cost_tracker.track_zenrows_request(request_id, zenrows_requests)

                if content_data:
                    await db_logger.log_content_sources(search_request_db_id, content_data)

                logger.info("Starting LLM analysis", extra={"request_id": request_id})
                final_response = await self._run_with_timeout(
                    self.llm_analyzer.analyze(query, content_data, request_id),
                    timeout=30.0,
                    stage_name="llm_analysis"
                )

                estimated_tokens = self._estimate_token_usage(query, content_data, final_response.answer)
                if estimated_tokens > 0:
                    await self.cost_tracker.track_llm_usage(request_id, estimated_tokens)

                processing_time = time.time() - start_time
                final_response.processing_time = processing_time
                final_response.cached = False

                request_cost = await self.cost_tracker.end_request(request_id)
                if request_cost:
                    final_response.cost_estimate = request_cost.total_cost

                await db_logger.update_search_response(
                    request_id=request_id,
                    response=final_response,
                    enhanced_queries=enhanced_queries,
                    status=RequestStatus.COMPLETED
                )

                if request_cost:
                    cost_breakdown = {
                        'brave_search': request_cost.brave_searches * self.cost_tracker.cost_rates["brave_search"],
                        'serpapi_search': request_cost.serpapi_searches * self.cost_tracker.cost_rates["serpapi_search"],
                        'zenrows': request_cost.zenrows_requests * self.cost_tracker.cost_rates["zenrows_request"],
                        'llm': request_cost.llm_tokens * self.cost_tracker.cost_rates["llm_token"]
                    }

                    usage_counts = {
                        'brave_searches': request_cost.brave_searches,
                        'serpapi_searches': request_cost.serpapi_searches,
                        'zenrows_requests': request_cost.zenrows_requests,
                        'llm_tokens': request_cost.llm_tokens
                    }

                    user_db_id = None
                    if user_id:
                        from app.database.repositories import UserRepository
                        user_repo = UserRepository(db_session)
                        user = await user_repo.get_user_by_identifier(user_id)
                        if user:
                            user_db_id = user.id

                    await db_logger.log_cost_record(
                        search_request_id=search_request_db_id,
                        user_id=user_db_id,
                        cost_breakdown=cost_breakdown,
                        usage_counts=usage_counts
                    )

                await self.cache.store_response(query, final_response)

                logger.info(f"Pipeline completed in {processing_time:.2f}s", 
                           extra={"request_id": request_id})

                return final_response

        except asyncio.TimeoutError as e:
            logger.error(f"Pipeline timeout: {str(e)}", extra={"request_id": request_id})
            if db_logger:
                await db_logger.mark_request_failed(
                    request_id=request_id,
                    error_message=f"Pipeline timeout: {str(e)}",
                    error_type="timeout"
                )
            await self.cost_tracker.handle_error(request_id, e)
            raise PipelineException("Request timed out. Please try again with a simpler query.")

        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}", extra={"request_id": request_id}, exc_info=True)
            if db_logger:
                await db_logger.mark_request_failed(
                    request_id=request_id,
                    error_message=str(e),
                    error_type="pipeline_error"
                )
            await self.cost_tracker.handle_error(request_id, e)
            raise PipelineException(f"Pipeline processing failed: {str(e)}")

    def _estimate_token_usage(self, query: str, content_data: List, response: str) -> int:
        try:
            query_tokens = len(query.split()) * 1.3
            content_tokens = 0
            for content in content_data[:3]:
                content_tokens += len(content.content.split()[:200]) * 1.3
            response_tokens = len(response.split()) * 1.3
            total_tokens = int(query_tokens + content_tokens + response_tokens)
            return max(total_tokens, 100)
        except Exception as e:
            logger.warning(f"Error estimating token usage: {e}")
            return 500

    async def _run_with_timeout(self, coro, timeout: float, stage_name: str):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Stage '{stage_name}' timed out after {timeout}s")
            raise asyncio.TimeoutError(f"Stage '{stage_name}' timed out")
        except Exception as e:
            logger.error(f"Stage '{stage_name}' failed: {str(e)}")
            raise

    async def health_check(self) -> Dict[str, str]:
        current_time = time.time()
        if current_time - self.last_health_check < 30:
            return {"overall": "healthy" if self.is_healthy else "unhealthy", "cached": True}

        try:
            health_tasks = {
                "query_enhancer": self._check_component_health(self.query_enhancer.health_check(), "query_enhancer"),
                "search_engine": self._check_component_health(self.search_engine.health_check(), "search_engine"),
                "content_fetcher": self._check_component_health(self.content_fetcher.health_check(), "content_fetcher"),
                "llm_analyzer": self._check_component_health(self.llm_analyzer.health_check(), "llm_analyzer"),
                "cache": self._check_component_health(self.cache.health_check(), "cache"),
                "database": self._check_database_health()
            }

            results = await asyncio.gather(*health_tasks.values(), return_exceptions=True)
            checks = {}
            for i, (component_name, _) in enumerate(health_tasks.items()):
                result = results[i]
                if isinstance(result, Exception):
                    checks[component_name] = "unhealthy"
                    logger.error(f"Health check failed for {component_name}: {result}")
                else:
                    checks[component_name] = result

            unhealthy = [k for k, v in checks.items() if v not in ["healthy", "degraded"]]
            self.is_healthy = len(unhealthy) <= 1
            overall = "healthy" if not unhealthy else "degraded" if len(unhealthy) == 1 else "unhealthy"
            self.last_health_check = current_time
            return {"overall": overall, **checks}
        except Exception as e:
            logger.error(f"Health check error: {e}")
            self.is_healthy = False
            return {"overall": "unhealthy", "error": str(e)}

    async def _check_database_health(self) -> str:
        try:
            async with db_manager.get_session_context() as session:
                await session.execute(text("SELECT 1"))
                return "healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return "unhealthy"

    async def _check_component_health(self, health_coro, component_name: str, timeout: float = 5.0):
        try:
            return await asyncio.wait_for(health_coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Health check timeout for {component_name}")
            return "timeout"
        except Exception as e:
            logger.error(f"Health check error for {component_name}: {e}")
            return "unhealthy"

    async def get_pipeline_stats(self) -> Dict:
        try:
            cost_stats = await self.cost_tracker.get_daily_stats()
            cache_status = await self.cache.health_check()
            db_stats = await self._get_database_stats()

            return {
                "daily_requests": cost_stats.get("request_count", 0),
                "daily_cost": cost_stats.get("total_cost", 0.0),
                "budget_utilization": cost_stats.get("budget_utilization", 0.0),
                "cache_status": cache_status,
                "pipeline_health": self.is_healthy,
                "last_health_check": self.last_health_check,
                "database": db_stats,
                "cost_breakdown": {
                    "brave_search": cost_stats.get("brave_search_cost", 0.0),
                    "serpapi_search": cost_stats.get("serpapi_search_cost", 0.0),
                    "zenrows": cost_stats.get("zenrows_cost", 0.0),
                    "llm": 0.0
                }
            }
        except Exception as e:
            logger.error(f"Error getting pipeline stats: {e}")
            return {"error": str(e)}

    async def _get_database_stats(self) -> Dict:
        try:
            async with db_manager.get_session_context() as session:
                from app.database.repositories import SearchRequestRepository
                repo = SearchRequestRepository(session)
                recent = await repo.get_recent_requests(hours=24)
                return {
                    "recent_requests_24h": len(recent),
                    "connection_status": "healthy"
                }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {"connection_status": "unhealthy", "error": str(e)}

    async def clear_cache(self, pattern: str = None):
        try:
            await self.cache.clear_cache(pattern)
            logger.info(f"Cache cleared with pattern: {pattern}")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            raise PipelineException(f"Failed to clear cache: {str(e)}")

    async def shutdown(self):
        try:
            logger.info("Shutting down pipeline components...")
            await asyncio.gather(
                self.query_enhancer.close(),
                self.search_engine.close(),
                self.content_fetcher.close(),
                self.llm_analyzer.close(),
                self.cache.close(),
                return_exceptions=True
            )
            logger.info("Pipeline shutdown completed")
        except Exception as e:
            logger.error(f"Error during pipeline shutdown: {e}")

    async def warm_up(self):
        try:
            logger.info("Warming up pipeline components...")
            test_query = "hello world"
            await self.query_enhancer.enhance(test_query)
            await self.search_engine.search_multiple([test_query], max_results_per_query=1)
            async with db_manager.get_session_context() as session:
                await session.execute(text("SELECT 1"))
            logger.info("Pipeline warm-up completed")
        except Exception as e:
            logger.warning(f"Pipeline warm-up error (non-critical): {e}")
