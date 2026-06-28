from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import os
import logging
import json

from core.protocols import KeyManager
from services.llm_service import generate_text_with_fallback
from db.database import Base, engine, get_db
from db.models import ApiKey
from routers import auth, keys

# Create tables on startup (TODO: replace with Alembic migrations)
Base.metadata.create_all(bind=engine)

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

app.include_router(auth.router)
app.include_router(keys.router)

security = HTTPBearer()

class ChatRequest(BaseModel):
    prompt: str = Field(..., description="The prompt to send to the LLM")

@app.get("/health", tags=["System"])
async def health_check():
    """Liveness probe endpoint for load balancer health checks."""
    return JSONResponse(
        status_code=200,
        content={"status": "alive", "service": "hydra-gateway"}
    )

@app.post("/v1/chat")
async def chat_endpoint(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    key_manager: KeyManager = Depends(get_key_manager)
):
    """
    Gateway entrypoint. Authenticates via hydra token, retrieves user's
    API keys from DB, enforces rate limits, and routes to LLM service.
    """
    # Resolve hydra token to user's API keys
    hydra_token = credentials.credentials
    api_key_record = db.query(ApiKey).filter(ApiKey.hydra_token == hydra_token).first()

    if not api_key_record:
        raise HTTPException(status_code=401, detail="Invalid hydra token")

    api_keys = json.loads(api_key_record.keys_blob)
    user_id = str(api_key_record.user_id)

    try:
        await key_manager.check_rate_limit(user_id, limit=100, window_seconds=60)

        result = await generate_text_with_fallback(
            prompt=request.prompt,
            user_id=user_id,
            api_keys=api_keys,
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