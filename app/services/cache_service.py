import asyncio
import json
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import redis.asyncio as redis  # Compatible with Python 3.11
from app.config.settings import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.max_memory_cache_size = settings.MEMORY_CACHE_SIZE
        self.redis_enabled = True

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        if not self.redis_enabled:
            return None

        if self.redis_client is None:
            try:
                if settings.REDIS_URL.startswith('redis://'):
                    self.redis_client = redis.from_url(
                        settings.REDIS_URL,
                        encoding="utf-8",
                        decode_responses=True,
                        socket_timeout=5,
                        socket_connect_timeout=5
                    )
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

    def _build_key(self, key: str, namespace: Optional[str]) -> str:
        return f"{namespace}:{key}" if namespace else key

    async def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        full_key = self._build_key(key, namespace)
        try:
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    value = await redis_client.get(full_key)
                    if value:
                        return json.loads(value)
                except Exception as e:
                    logger.warning(f"Redis get error: {e}")

            # Memory fallback
            if full_key in self.memory_cache:
                entry = self.memory_cache[full_key]
                if datetime.now() < entry['expires']:
                    return entry['value']
                else:
                    del self.memory_cache[full_key]

        except Exception as e:
            logger.error(f"Cache get error: {e}")

        return None

    async def set(self, key: str, value: Any, ttl: int = 3600, namespace: Optional[str] = None) -> bool:
        full_key = self._build_key(key, namespace)
        try:
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    await redis_client.setex(full_key, ttl, json.dumps(value, default=str))
                except Exception as e:
                    logger.warning(f"Redis set error: {e}")

            if len(self.memory_cache) >= self.max_memory_cache_size:
                self.memory_cache.pop(next(iter(self.memory_cache)))

            self.memory_cache[full_key] = {
                'value': value,
                'expires': datetime.now() + timedelta(seconds=ttl)
            }

            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        full_key = self._build_key(key, namespace)
        try:
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    await redis_client.delete(full_key)
                except Exception as e:
                    logger.warning(f"Redis delete error: {e}")

            self.memory_cache.pop(full_key, None)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def clear_pattern(self, pattern: str, namespace: Optional[str] = None) -> bool:
        full_pattern = self._build_key(pattern, namespace)
        try:
            redis_client = await self._get_redis_client()
            if redis_client:
                try:
                    keys = await redis_client.keys(full_pattern)
                    if keys:
                        await redis_client.delete(*keys)
                except Exception as e:
                    logger.warning(f"Redis clear pattern error: {e}")

            keys_to_delete = [k for k in self.memory_cache if full_pattern.replace('*', '') in k]
            for k in keys_to_delete:
                del self.memory_cache[k]

            return True
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return False

    async def health_check(self) -> str:
        try:
            test_key = "health_check"
            await self.set(test_key, "test", 5)
            value = await self.get(test_key)
            await self.delete(test_key)
            if value == "test":
                return "healthy"
            return "unhealthy"
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return "unhealthy"

    async def close(self):
        if self.redis_client:
            try:
                await self.redis_client.aclose()
            except Exception:
                pass
        self.memory_cache.clear()
