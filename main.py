from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import os
import logging

from core.protocols import KeyManager
from services.llm_service import generate_text_with_fallback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MANAGER_TYPE = os.getenv("MANAGER_TYPE", "redis").lower()

if MANAGER_TYPE == "redis":
    from core.redis_manager import get_redis_manager as get_key_manager
    logger.info("[System] Initializing Gateway with RedisManager (Distributed Mode)")
else:
    from core.memory_manager import get_memory_manager as get_key_manager
    logger.info("[System] Initializing Gateway with MemoryManager (Local Mode)")

app = FastAPI(
    title="Hydra-LLM API Gateway",
    description="Enterprise-grade BYOK Gateway featuring strictly decoupled Dependency Injection.",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user making the request")
    api_keys: list[str] = Field(..., min_items=1, description="List of Gemini API keys provided by the user")
    prompt: str = Field(..., description="The prompt to send to the LLM")

@app.get("/health", tags=["System"])
async def health_check():
    """
    Liveness probe endpoint for GCP Cloud Run.
    Cloud Run constantly pings this endpoint to ensure the container is healthy.
    It must return a 200 OK status within a specific timeframe.
    """
    return JSONResponse(
        status_code=200,
        content={"status": "alive", "service": "hydra-gateway"}
    )

@app.post("/v1/chat")
async def chat_endpoint(
    request: ChatRequest,
    key_manager: KeyManager = Depends(get_key_manager)  # <-- FASTAPI NATIVE DI
):
    """
    Gateway entrypoint. Resolves the KeyManager dependency automatically via FastAPI,
    enforces rate limits, and routes the validated request to the service layer.
    """
    try:
        # Enforce rate limit (100 requests per 60 seconds for demonstration)
        await key_manager.check_rate_limit(request.user_id, limit=100, window_seconds=60)

        # Execute business logic with the injected dependency
        result = await generate_text_with_fallback(
            prompt=request.prompt, 
            user_id=request.user_id, 
            api_keys=request.api_keys,
            key_manager=key_manager
        )
        
        clean_text = result["candidates"][0]["content"]["parts"][0]["text"]
        return {"status": "success", "data": clean_text}
        
    except KeyError:
        return {"status": "error", "message": "Failed to parse LLM response"}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")