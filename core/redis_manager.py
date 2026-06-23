import redis.asyncio as redis
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class RedisManager:
    """
    Concrete implementation of the KeyManager protocol using Redis.
    Provides atomic operations for distributed systems.
    """
    def __init__(self, redis_url: str = "redis://127.0.0.1:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def get_next_key(self, user_id: str, api_keys: list[str]) -> str:
        pool_size = len(api_keys)
        if pool_size == 0:
            raise ValueError("API key list cannot be empty.")

        redis_key = f"user:{user_id}:key_index"
        
        # INCR guarantees atomicity, preventing race conditions across multiple workers
        current_count = await self.redis.incr(redis_key)
        current_index = (current_count - 1) % pool_size
        
        selected_key = api_keys[current_index]
        logger.info(f"User {user_id} assigned Key ending in ...{selected_key[-4:]}")
        
        return selected_key

    async def check_rate_limit(self, user_id: str, limit: int = 60, window_seconds: int = 60) -> None:
        rate_limit_key = f"rate_limit:{user_id}"
        
        current_requests = await self.redis.incr(rate_limit_key)
        
        if current_requests == 1:
            await self.redis.expire(rate_limit_key, window_seconds)
            
        if current_requests > limit:
            logger.warning(f"User {user_id} triggered Rate Limit ({current_requests}/{limit})")
            raise HTTPException(
                status_code=429, 
                detail=f"Rate limit exceeded. Maximum {limit} requests per {window_seconds} seconds."
            )

# Singleton instance
redis_client = RedisManager()

# FastAPI Dependency Provider
async def get_key_manager() -> RedisManager:
    """
    Dependency provider function to be used with FastAPI's Depends().
    This allows easy mocking of the KeyManager during unit testing.
    """
    return redis_client