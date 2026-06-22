import httpx
import logging
from fastapi import HTTPException
from core.balancer import KeyBalancer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

async def generate_text_with_fallback(prompt: str, balancer: KeyBalancer) -> dict:
    """
    Calls the Gemini API using httpx. 
    Implements automatic fallback if a key encounters rate limits or server errors.
    """
    max_retries = balancer.pool_size
    attempts = 0

    # httpx.AsyncClient ensures non-blocking network calls
    async with httpx.AsyncClient() as client:
        while attempts < max_retries:
            current_key = balancer.get_next_key()
            # url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={current_key}"
            MODEL_NAME = "gemini-3-flash-preview"
            url = f"http://127.0.0.1:8001/v1beta/models/{MODEL_NAME}:generateContent?key={current_key}"

            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }

            try:
                # Set a 10-second timeout to prevent hanging requests
                response = await client.post(url, json=payload, timeout=10.0)
                
                # Check for Rate Limit (429) or Server Errors (5xx)
                if response.status_code in [429, 500, 503]:
                    logger.warning(f"Key ...{current_key[-4:]} failed with status {response.status_code}. Fallback triggered.")
                    attempts += 1
                    continue # Try the next key in the loop
                
                response.raise_for_status()
                return response.json()

            except httpx.RequestError as exc:
                logger.error(f"Network error with key ...{current_key[-4:]}: {exc}. Fallback triggered.")
                attempts += 1
                continue

    # If the loop finishes and all attempts failed
    logger.error("All API keys in the pool have been exhausted or failed.")
    raise HTTPException(status_code=503, detail="Service Unavailable: All upstream resources exhausted.")