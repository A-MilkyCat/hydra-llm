from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from core.balancer import KeyBalancer
from services.llm_service import generate_text_with_fallback

app = FastAPI(
    title="Hydra-LLM API Gateway",
    description="BYOK (Bring Your Own Key) Gateway with Per-User Round-Robin",
    version="1.0.0"
)

# In-memory storage mapping user_id to their specific KeyBalancer
# Note: In a production environment with multiple workers, this should be replaced by Redis.
user_balancers: dict[str, KeyBalancer] = {}

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user making the request")
    api_keys: list[str] = Field(..., min_items=1, description="List of Gemini API keys provided by the user")
    prompt: str = Field(..., description="The prompt to send to the LLM")

@app.post("/v1/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Receives user-specific keys and a prompt, then routes it through the load-balanced LLM service.
    """
    user_id = request.user_id
    user_keys = request.api_keys

    # Check if the user is new, or if they have updated their provided key list
    if user_id not in user_balancers or user_balancers[user_id].keys != user_keys:
        print(f"[Gateway] Initializing new KeyBalancer for user: {user_id}")
        user_balancers[user_id] = KeyBalancer(user_keys)

    # Retrieve the user's specific balancer instance
    balancer = user_balancers[user_id]

    try:
        # Pass the user's prompt and their specific balancer to the service
        result = await generate_text_with_fallback(request.prompt, balancer)
        
        clean_text = result["candidates"][0]["content"]["parts"][0]["text"]
        return {"status": "success", "data": clean_text}
        
    except KeyError:
        return {"status": "error", "message": "Failed to parse LLM response", "raw_data": result}
    except HTTPException as http_exc:
        raise http_exc
    # Fallback for unexpected internal errors
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))