# app/services/cache_service.py - Fixed for Python 3.11 compatibility
import asyncio
import json
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta

# Use redis instead of aioredis for Python 3.11 compatibility
import redis.asyncio as redis  # This works with Python 3.11
from app.config.settings import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.max_memory_cache_size = settings.MEMORY_CACHE_SIZE
        self.redis_enabled = True
        
    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get or create Redis client with error handling"""
        if not self.redis_enabled:
            return None
            
        if self.redis_client is None:
            try:
                # Parse Redis URL
                if settings.REDIS_URL.startswith('redis://'):
                    self.redis_client = redis.from_url(
                        settings.REDIS_URL,
                        encoding="utf-8",
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5
                    )
                    # Test connection
                    await self.redis_client.ping()
                    logger.info("✅ Redis connection established")
                else:
                    logger.warning("⚠️ Invalid Redis URL, using memory cache only")
                    self.redis_enabled = False
                    return None
                    
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed: {e}. Using memory cache only.")
                self.redis_enabled = False
                return None
                
        return self.redis_client

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (Redis first, then memory)"""
        try:
            # Try Redis first
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    value = await redis_client.get(key)
                    if value:
                        return json.loads(value)
                except Exception as e:
                    logger.warning(f"Redis get error: {e}")
            
            # Fallback to memory cache
            if key in self.memory_cache:
                cache_entry = self.memory_cache[key]
                if datetime.now() < cache_entry['expires']:
                    return cache_entry['value']
                else:
                    # Expired, remove it
                    del self.memory_cache[key]
                    
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache (Redis and memory)"""
        try:
            # Store in Redis
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    await redis_client.setex(
                        key, 
                        ttl, 
                        json.dumps(value, default=str)
                    )
                except Exception as e:
                    logger.warning(f"Redis set error: {e}")
            
            # Store in memory cache as backup
            if len(self.memory_cache) >= self.max_memory_cache_size:
                # Remove oldest entry
                oldest_key = next(iter(self.memory_cache))
                del self.memory_cache[oldest_key]
                
            self.memory_cache[key] = {
                'value': value,
                'expires': datetime.now() + timedelta(seconds=ttl)
            }
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            # Delete from Redis
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    await redis_client.delete(key)
                except Exception as e:
                    logger.warning(f"Redis delete error: {e}")
            
            # Delete from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
                
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> bool:
        """Clear all keys matching pattern"""
        try:
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    keys = await redis_client.keys(pattern)
                    if keys:
                        await redis_client.delete(*keys)
                except Exception as e:
                    logger.warning(f"Redis clear pattern error: {e}")
            
            # Clear from memory cache
            keys_to_delete = [k for k in self.memory_cache.keys() if pattern.replace('*', '') in k]
            for key in keys_to_delete:
                del self.memory_cache[key]
                
            return True
            
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return False

    async def health_check(self) -> str:
        """Check cache service health"""
        try:
            # Test memory cache
            test_key = "health_check_test"
            await self.set(test_key, "test_value", 10)
            value = await self.get(test_key)
            await self.delete(test_key)
            
            if value == "test_value":
                redis_client = await self._get_redis_client()
                if redis_client:
                    return "healthy"  # Both Redis and memory working
                else:
                    return "healthy"  # Memory cache working, Redis optional
            else:
                return "unhealthy"
                
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return "unhealthy"

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            redis_info = {}
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    info = await redis_client.info()
                    redis_info = {
                        "connected": True,
                        "used_memory": info.get("used_memory_human", "unknown"),
                        "keyspace_hits": info.get("keyspace_hits", 0),
                        "keyspace_misses": info.get("keyspace_misses", 0)
                    }
                except:
                    redis_info = {"connected": False}
            else:
                redis_info = {"connected": False}
                
            return {
                "redis": redis_info,
                "memory_cache": {
                    "size": len(self.memory_cache),
                    "max_size": self.max_memory_cache_size
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}

    async def close(self):
        """Close cache connections"""
        if self.redis_client:
            try:
                await self.redis_client.aclose()
            except:
                pass
        self.memory_cache.clear()

# Backward compatibility functions
async def store_query_enhancement(query: str, enhanced_queries: list) -> bool:
    """Store query enhancement in cache"""
    cache = CacheService()
    cache_key = f"query_enhancement:{hash(query)}"
    return await cache.set(cache_key, enhanced_queries, settings.CACHE_TTL_QUERY_ENHANCEMENT)

async def get_query_enhancement(query: str) -> Optional[list]:
    """Get query enhancement from cache"""
    cache = CacheService()
    cache_key = f"query_enhancement:{hash(query)}"
    return await cache.get(cache_key)

async def store_search_results(query: str, results: list) -> bool:
    """Store search results in cache"""
    cache = CacheService()
    cache_key = f"search_results:{hash(query)}"
    return await cache.set(cache_key, results, settings.CACHE_TTL_SEARCH_RESULTS)

async def get_search_results(query: str) -> Optional[list]:
    """Get search results from cache"""
    cache = CacheService()
    cache_key = f"search_results:{hash(query)}"
    return await cache.get(cache_key)

async def store_response(query: str, response_data: dict) -> bool:
    """Store final response in cache"""
    cache = CacheService()
    cache_key = f"final_response:{hash(query)}"
    return await cache.set(cache_key, response_data, settings.CACHE_TTL_FINAL_RESPONSE)

async def get_response(query: str) -> Optional[dict]:
    """Get final response from cache"""
    cache = CacheService()
    cache_key = f"final_response:{hash(query)}"
    return await cache.get(cache_key)
