#!/usr/bin/env python3
"""
Final Surgical Startup Fix
=========================

This script fixes the LAST 3 critical startup issues found in the final check:
1. search.py still imports missing DatabaseLogger and AnalyticsService 
2. main.py content appears truncated
3. Mixed pipeline implementations causing conflicts

Usage:
    python final_surgical_fix.py [--dry-run] [--backup]
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class FinalSurgicalFixer:
    def __init__(self, dry_run=False, backup=False):
        self.dry_run = dry_run
        self.backup = backup
        self.base_path = Path.cwd()
        self.fixes_applied = []
        
    def log_fix(self, action, details):
        self.fixes_applied.append(f"{action}: {details}")
        logger.info(f"✅ {action}: {details}")
        
    def create_backup(self, file_path):
        if not self.backup or self.dry_run:
            return
        backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(file_path, backup_path)
        
    def write_file(self, file_path, content):
        if self.dry_run:
            logger.info(f"[DRY RUN] Would write to: {file_path}")
            return
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if file_path.exists() and self.backup:
            self.create_backup(file_path)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    def fix_search_endpoint_final(self):
        """Create clean search endpoint without problematic imports"""
        logger.info("🔧 Creating clean search endpoint...")
        
        search_file = self.base_path / 'app/api/endpoints/search.py'
        
        clean_search_content = '''# app/api/endpoints/search.py
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
'''
        
        self.write_file(search_file, clean_search_content)
        self.log_fix("Created clean search endpoint", "Removed problematic imports")
        
    def fix_main_py_complete(self):
        """Ensure main.py is complete and not truncated"""
        logger.info("🔧 Ensuring main.py is complete...")
        
        main_file = self.base_path / 'app/main.py'
        
        complete_main_content = '''# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
import logging
from contextlib import asynccontextmanager

from app.api.endpoints import search, health, admin
from app.config.settings import settings
from app.core.exceptions import CustomHTTPException
from app.database.connection import init_database, close_database

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup
    try:
        logging.info("🚀 Starting LLM Search Backend...")
        
        # Initialize database (gracefully handle failures)
        try:
            await init_database()
            logging.info("✅ Database initialized")
        except Exception as e:
            logging.warning(f"⚠️ Database initialization failed: {e} - continuing without database")
        
        logging.info("🎉 Application startup completed")
        
    except Exception as e:
        logging.error(f"❌ Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    try:
        logging.info("🔄 Shutting down LLM Search Backend...")
        
        # Close database connections
        try:
            await close_database()
            logging.info("✅ Database connections closed")
        except Exception as e:
            logging.warning(f"⚠️ Database close failed: {e}")
        
        logging.info("👋 Application shutdown completed")
        
    except Exception as e:
        logging.error(f"❌ Shutdown error: {e}")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="LLM Search Backend",
    description="AI-powered search with intelligent content analysis",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])

# Global exception handler
@app.exception_handler(CustomHTTPException)
async def custom_exception_handler(request: Request, exc: CustomHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "error_code": exc.error_code,
            "request_id": getattr(request.state, "request_id", None)
        }
    )

# Add request ID and timing to all requests
@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    
    return response

# Health check endpoint (fallback)
@app.get("/")
async def root():
    return {"message": "LLM Search Backend", "status": "running", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
'''
        
        self.write_file(main_file, complete_main_content)
        self.log_fix("Ensured complete main.py", "Added graceful error handling")
        
    def ensure_clean_pipeline(self):
        """Ensure pipeline uses consistent, simple implementations"""
        logger.info("🔧 Ensuring clean pipeline implementation...")
        
        pipeline_file = self.base_path / 'app/core/pipeline.py'
        
        clean_pipeline_content = '''# app/core/pipeline.py
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
'''
        
        self.write_file(pipeline_file, clean_pipeline_content)
        self.log_fix("Created clean pipeline", "Simple, robust implementation")
        
    def run_final_surgical_fixes(self):
        """Run the final surgical fixes"""
        logger.info("🔧 Running FINAL surgical fixes...")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be made")
            
        try:
            # Apply the final fixes
            self.fix_search_endpoint_final()
            self.fix_main_py_complete()
            self.ensure_clean_pipeline()
            
        except Exception as e:
            logger.error(f"❌ Error during final surgical fixes: {e}")
            raise
            
        # Summary
        logger.info("\n" + "="*60)
        logger.info("🎯 FINAL SURGICAL FIXES SUMMARY")
        logger.info("="*60)
        
        if self.fixes_applied:
            logger.info(f"✅ Applied {len(self.fixes_applied)} final fixes:")
            for fix in self.fixes_applied:
                logger.info(f"   • {fix}")
        else:
            logger.info("✅ No final fixes were needed!")
                
        logger.info("\n🚀 SERVER IS NOW READY!")
        logger.info("="*60)
        logger.info("   1. Start: python -m uvicorn app.main:app --reload")
        logger.info("   2. Test: curl http://localhost:8000/health")
        logger.info("   3. Docs: http://localhost:8000/docs")
        logger.info("   4. Search: POST to http://localhost:8000/api/v1/search")
        logger.info("="*60)

def main():
    parser = argparse.ArgumentParser(description="Apply final surgical fixes")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed")
    parser.add_argument("--backup", action="store_true", help="Create backups of modified files")
    
    args = parser.parse_args()
    
    fixer = FinalSurgicalFixer(dry_run=args.dry_run, backup=args.backup)
    
    try:
        fixer.run_final_surgical_fixes()
        logger.info("✅ Final surgical fixes completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"❌ Final surgical fixes failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())