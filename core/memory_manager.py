import asyncio
from collections import defaultdict
from fastapi import HTTPException
import time
import logging

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    A KeyManager implementation using Python dictionaries.
    This can perfectly substitute RedisManager for performance and behavior comparisons.
    """
    def __init__(self):
        # Store the rotation index for each user
        self.user_indexes = defaultdict(int)
        # Store the rate limit state for each user
        self.rate_limits = defaultdict(lambda: {"count": 0, "reset_time": 0})
        # An asyncio.Lock is strictly required in-memory to prevent Race Conditions 
        # when multiple async workers/coroutines access the dictionary simultaneously.
        self.lock = asyncio.Lock()

    async def get_next_key(self, user_id: str, api_keys: list[str]) -> str:
        pool_size = len(api_keys)
        if pool_size == 0:
            raise ValueError("API key list cannot be empty.")

        # Use asyncio.Lock to ensure atomicity (simulating the behavior of Redis INCR)
        async with self.lock:
            current_index = self.user_indexes[user_id]
            self.user_indexes[user_id] = (current_index + 1) % pool_size

        selected_key = api_keys[current_index]
        logger.info(f"[Memory] User {user_id} assigned Key ...{selected_key[-4:]} (Index: {current_index})")
        return selected_key

    async def check_rate_limit(self, user_id: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        async with self.lock:
            user_record = self.rate_limits[user_id]
            if now > user_record["reset_time"]:
                user_record["count"] = 1
                user_record["reset_time"] = now + window_seconds
            else:
                user_record["count"] += 1
            current_requests = user_record["count"]

        if current_requests > limit:
            logger.warning(f"[Memory] User {user_id} triggered rate limit ({current_requests}/{limit})")
            raise HTTPException(status_code=429, detail="Rate limit exceeded.")

# Create a singleton instance for FastAPI dependency injection
memory_client = MemoryManager()

async def get_memory_manager():
    """Dependency injection provider for FastAPI"""
    return memory_client