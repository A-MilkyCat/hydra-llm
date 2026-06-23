from typing import Protocol

class KeyManager(Protocol):
    """
    Interface (Contract) for any dependency that manages API key state.
    By depending on this protocol, the service layer remains completely decoupled
    from concrete implementations like Redis or Memory.
    """
    async def get_next_key(self, user_id: str, api_keys: list[str]) -> str:
        """Atomically retrieves the next API key in the rotation."""
        ...
        
    async def check_rate_limit(self, user_id: str, limit: int, window_seconds: int) -> None:
        """Validates if the user has exceeded their request quota."""
        ...