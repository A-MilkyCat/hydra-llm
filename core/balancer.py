import logging

logger = logging.getLogger(__name__)

class KeyBalancer:
    """
    Implements a Round-Robin load balancer for API keys.
    """
    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("API key list cannot be empty.")
        self._keys = keys
        self._pool_size = len(keys)
        self._current_index = 0

    def get_next_key(self) -> str:
        key = self._keys[self._current_index]
        self._current_index = (self._current_index + 1) % self._pool_size
        logger.info(f"Using API Key ending in ...{key[-4:]}")
        return key

    @property
    def pool_size(self) -> int:
        return self._pool_size

    @property
    def keys(self) -> list[str]:
        return self._keys