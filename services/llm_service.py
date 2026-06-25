import httpx
import logging
from fastapi import HTTPException
from core.protocols import KeyManager
import os

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Dynamically route the API base URL.
# If not set, it defaults to the REAL Google Gemini API.
# For testing, you can set this to "http://127.0.0.1:8001" or your Cloud Run Mock URL.
GEMINI_API_BASE_URL = os.getenv(
    "GEMINI_API_BASE_URL", 
    "https://generativelanguage.googleapis.com"
)

async def generate_text_with_fallback(
    prompt: str, 
    user_id: str, 
    api_keys: list[str], 
    key_manager: KeyManager  # <--- Dependency Injection
) -> dict:
    """
    Calls the LLM API using httpx. 
    Relies on an injected KeyManager to retrieve the next key.
    """
    max_retries = len(api_keys)
    attempts = 0

    async with httpx.AsyncClient() as client:
        while attempts < max_retries:
            # Delegate key selection to the injected dependency
            current_key = await key_manager.get_next_key(user_id, api_keys)
            
            MODEL_NAME = "gemini-3-flash-preview"
            url = f"{GEMINI_API_BASE_URL}/v1beta/models/{MODEL_NAME}:generateContent?key={current_key}"

            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }

            try:
                response = await client.post(url, json=payload, timeout=10.0)
                
                if response.status_code in [429, 500, 503]:
                    logger.warning(f"Key ...{current_key[-4:]} failed with status {response.status_code}. Fallback triggered.")
                    attempts += 1
                    continue
                
                response.raise_for_status()
                return response.json()

            except httpx.RequestError as exc:
                logger.error(f"Network error with key ...{current_key[-4:]}: {exc}. Fallback triggered.")
                attempts += 1
                continue

    logger.error("All API keys in the pool have been exhausted or failed.")
    raise HTTPException(status_code=503, detail="Service Unavailable: All upstream resources exhausted.")