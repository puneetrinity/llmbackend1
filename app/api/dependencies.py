# app/api/dependencies.py
import time
import logging
from typing import Optional, Dict
from fastapi import Depends, HTTPException, Request
from functools import lru_cache

from app.core.pipeline import SearchPipeline
from app.services.cache_service import CacheService
from app.config.settings import settings
from app.core.exceptions import RateLimitException

logger = logging.getLogger(__name__)

# Global pipeline instance
_pipeline_instance: Optional[SearchPipeline] = None

@lru_cache()
def get_pipeline() -> SearchPipeline:
    """Get or create pipeline instance (singleton)"""
    global _pipeline_instance
    
    if _pipeline_instance is None:
        _pipeline_instance = SearchPipeline()
        logger.info("Pipeline instance created")
    
    return _pipeline_instance

async def get_current_user(request: Request) -> Optional[str]:
    """
    Extract user ID from request (simplified authentication)
    In production, this would validate JWT tokens, API keys, etc.
    """
    try:
        # Check for API key in headers
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # In production, validate API key against database
            return f"api_user_{hash(api_key) % 10000}"
        
        # Check for user ID in headers (for demo purposes)
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return user_id
        
        # For demo, use IP address as user identifier
        client_ip = request.client.host
        return f"ip_{client_ip.replace('.', '_')}"
        
    except Exception as e:
        logger.warning(f"Error extracting user ID: {e}")
        return None

# Rate limiting storage
_rate_limit_cache: Dict[str, Dict] = {}

async def rate_limit(request: Request, current_user: str = Depends(get_current_user)):
    """
    Simple rate limiting based on user/IP
    In production, use Redis for distributed rate limiting
    """
    try:
        # Use user ID or IP for rate limiting
        identifier = current_user or request.client.host
        current_time = time.time()
        
        # Clean up old entries (simple cleanup)
        if len(_rate_limit_cache) > 10000:  # Prevent memory bloat
            cutoff_time = current_time - 3600  # 1 hour ago
            expired_keys = [k for k, v in _rate_limit_cache.items() 
                          if v.get('last_reset', 0) < cutoff_time]
            for key in expired_keys:
                del _rate_limit_cache[key]
        
        # Get or create rate limit data for this identifier
        if identifier not in _rate_limit_cache:
            _rate_limit_cache[identifier] = {
                'requests': 0,
                'last_reset': current_time
            }
        
        rate_data = _rate_limit_cache[identifier]
        
        # Reset counter if a minute has passed
        if current_time - rate_data['last_reset'] >= 60:  # 60 seconds
            rate_data['requests'] = 0
            rate_data['last_reset'] = current_time
        
        # Check rate limit
        if rate_data['requests'] >= settings.RATE_LIMIT_PER_MINUTE:
            logger.warning(f"Rate limit exceeded for {identifier}")
            raise RateLimitException(
                detail=f"Rate limit exceeded. Maximum {settings.RATE_LIMIT_PER_MINUTE} requests per minute."
            )
        
        # Increment request counter
        rate_data['requests'] += 1
        
        return True
        
    except RateLimitException:
        raise
    except Exception as e:
        logger.error(f"Rate limiting error: {e}")
        # Fail open - don't block requests if rate limiting fails
        return True

async def check_content_length(request: Request):
    """Check request content length"""
    try:
        content_length = request.headers.get("content-length")
        if content_length:
            length = int(content_length)
            max_length = 10 * 1024  # 10KB max
            if length > max_length:
                raise HTTPException(
                    status_code=413,
                    detail=f"Request too large. Maximum size: {max_length} bytes"
                )
    except ValueError:
        pass  # Ignore invalid content-length headers
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Content length check error: {e}")

async def validate_request_id(request: Request) -> str:
    """Get or validate request ID"""
    request_id = getattr(request.state, 'request_id', None)
    if not request_id:
        request_id = f"req_{int(time.time() * 1000)}"
        request.state.request_id = request_id
    return request_id

async def log_request_info(
    request: Request, 
    user_id: str = Depends(get_current_user)
):
    """Log request information for monitoring"""
    try:
        log_data = {
            "method": request.method,
            "url": str(request.url),
            "user_id": user_id,
            "user_agent": request.headers.get("user-agent", ""),
            "request_id": getattr(request.state, 'request_id', 'unknown')
        }
        
        logger.info(f"Request: {log_data}")
        
    except Exception as e:
        logger.warning(f"Request logging error: {e}")

# Dependency for admin operations (simplified)
async def require_admin(request: Request):
    """
    Require admin privileges for certain operations
    In production, this would check proper admin authentication
    """
    admin_key = request.headers.get("X-Admin-Key")
    if admin_key != settings.SECRET_KEY:  # Simplified admin check
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    return True

# Health check dependencies
async def get_cache_service() -> CacheService:
    """Get cache service instance"""
    return CacheService()

# Startup/shutdown handlers
async def startup_handler():
    """Application startup handler"""
    try:
        logger.info("Starting up application...")
        
        # Initialize pipeline and warm up
        pipeline = get_pipeline()
        await pipeline.warm_up()
        
        logger.info("Application startup completed")
        
    except Exception as e:
        logger.error(f"Startup error: {e}")

async def shutdown_handler():
    """Application shutdown handler"""
    try:
        logger.info("Shutting down application...")
        
        global _pipeline_instance
        if _pipeline_instance:
            await _pipeline_instance.shutdown()
            _pipeline_instance = None
        
        logger.info("Application shutdown completed")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# Custom exception handlers
async def handle_pipeline_exception(request: Request, exc: Exception):
    """Handle pipeline-specific exceptions"""
    logger.error(f"Pipeline exception: {exc}")
    return HTTPException(status_code=500, detail=str(exc))

async def handle_rate_limit_exception(request: Request, exc: RateLimitException):
    """Handle rate limit exceptions"""
    return HTTPException(
        status_code=429,
        detail=exc.detail,
        headers={"Retry-After": "60"}
    )
