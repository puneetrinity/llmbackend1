# app/services/cache_service.py
import asyncio
import json
import logging
import hashlib
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import aioredis
from functools import lru_cache

from app.config.settings import settings
from app.core.exceptions import CacheException
from app.models.responses import SearchResponse
from app.models.internal import QueryEnhancement

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        self.memory_cache_timestamps = {}
        self.max_memory_cache_size = settings.MEMORY_CACHE_SIZE
        
    async def _get_redis_client(self):
        """Lazy initialization of Redis client"""
        if self.redis_client is None:
            try:
                self.redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self.redis_client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Using memory cache only.")
                self.redis_client = None
        return self.redis_client
    
    def _generate_cache_key(self, key: str, prefix: str = "search") -> str:
        """Generate a consistent cache key"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    async def get_response(self, query: str) -> Optional[SearchResponse]:
        """Get cached search response"""
        cache_key = self._generate_cache_key(query, "response")
        
        # Try memory cache first
        if cache_key in self.memory_cache:
            cached_data, timestamp = self.memory_cache[cache_key], self.memory_cache_timestamps[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=settings.CACHE_TTL_FINAL_RESPONSE):
                logger.info(f"Memory cache hit for query: {query[:30]}...")
                return SearchResponse(**cached_data)
            else:
                # Remove expired entry
                del self.memory_cache[cache_key]
                del self.memory_cache_timestamps[cache_key]
        
        # Try Redis cache
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    logger.info(f"Redis cache hit for query: {query[:30]}...")
                    data = json.loads(cached_data)
                    response = SearchResponse(**data)
                    
                    # Store in memory cache for faster access
                    self._store_in_memory_cache(cache_key, data)
                    return response
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        return None
    
    async def store_response(self, query: str, response: SearchResponse):
        """Store search response in cache"""
        cache_key = self._generate_cache_key(query, "response")
        data = response.dict()
        
        # Store in memory cache
        self._store_in_memory_cache(cache_key, data)
        
        # Store in Redis cache
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key, 
                    settings.CACHE_TTL_FINAL_RESPONSE,
                    json.dumps(data, default=str)
                )
                logger.info(f"Cached response for query: {query[:30]}...")
            except Exception as e:
                logger.error(f"Redis set error: {e}")
    
    def _store_in_memory_cache(self, key: str, data: Any):
        """Store data in memory cache with size limit"""
        # Clean up if cache is full
        if len(self.memory_cache) >= self.max_memory_cache_size:
            # Remove oldest entries (simple LRU)
            oldest_key = min(self.memory_cache_timestamps.keys(), 
                           key=lambda k: self.memory_cache_timestamps[k])
            del self.memory_cache[oldest_key]
            del self.memory_cache_timestamps[oldest_key]
        
        self.memory_cache[key] = data
        self.memory_cache_timestamps[key] = datetime.now()
    
    async def get(self, key: str, prefix: str = "general") -> Optional[Any]:
        """Generic get method for any cacheable data"""
        cache_key = self._generate_cache_key(key, prefix)
        
        # Try memory cache first
        if cache_key in self.memory_cache:
            cached_data, timestamp = self.memory_cache[cache_key], self.memory_cache_timestamps[cache_key]
            # Use different TTL based on prefix
            ttl = self._get_ttl_by_prefix(prefix)
            if datetime.now() - timestamp < timedelta(seconds=ttl):
                return cached_data
            else:
                del self.memory_cache[cache_key]
                del self.memory_cache_timestamps[cache_key]
        
        # Try Redis cache
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    self._store_in_memory_cache(cache_key, data)
                    return data
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = None, prefix: str = "general"):
        """Generic set method for any cacheable data"""
        cache_key = self._generate_cache_key(key, prefix)
        
        if ttl is None:
            ttl = self._get_ttl_by_prefix(prefix)
        
        # Store in memory cache
        self._store_in_memory_cache(cache_key, value)
        
        # Store in Redis cache
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                await redis_client.setex(
                    cache_key, 
                    ttl,
                    json.dumps(value, default=str)
                )
            except Exception as e:
                logger.error(f"Redis set error: {e}")
    
    def _get_ttl_by_prefix(self, prefix: str) -> int:
        """Get TTL based on cache prefix"""
        ttl_map = {
            "response": settings.CACHE_TTL_FINAL_RESPONSE,
            "enhancement": settings.CACHE_TTL_QUERY_ENHANCEMENT,
            "search": settings.CACHE_TTL_SEARCH_RESULTS,
            "general": 3600
        }
        return ttl_map.get(prefix, 3600)
    
    async def health_check(self) -> str:
        """Check cache service health"""
        try:
            # Test memory cache
            test_key = "health_check"
            self._store_in_memory_cache(test_key, {"test": True})
            
            # Test Redis cache
            redis_client = await self._get_redis_client()
            if redis_client:
                await redis_client.ping()
                return "healthy"
            else:
                return "memory_only"  # Redis unavailable but memory cache works
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return "unhealthy"
    
    async def clear_cache(self, pattern: str = None):
        """Clear cache entries matching pattern"""
        # Clear memory cache
        if pattern:
            keys_to_remove = [k for k in self.memory_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self.memory_cache[key]
                del self.memory_cache_timestamps[key]
        else:
            self.memory_cache.clear()
            self.memory_cache_timestamps.clear()
        
        # Clear Redis cache
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                if pattern:
                    keys = await redis_client.keys(f"*{pattern}*")
                    if keys:
                        await redis_client.delete(*keys)
                else:
                    await redis_client.flushdb()
            except Exception as e:
                logger.error(f"Redis clear error: {e}")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
