from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import asyncio
from collections import defaultdict

# Create a micro FastAPI application for testing purposes
app = FastAPI(title="Mock Gemini Server")

# In-memory dictionary to track API key usage counts
# Format: {"AIzaSy_key_A": 5, "AIzaSy_key_B": 8}
key_usage_tracker = defaultdict(int)

@app.post("/v1beta/models/{model_name}:generateContent")
async def mock_gemini_endpoint(model_name: str, key: str = Query(None)):
    """
    A mock endpoint for the Gemini API.
    It intercepts the request and simulates network latency and rate limits.
    """
    if not key:
        return JSONResponse(status_code=401, content={"error": "API key not valid."})

    # 1. Simulate network and AI processing latency
    # (15.71 seconds / 7 requests = approx 2.24 seconds)
    await asyncio.sleep(2.24)

    # 2. Increment the usage count for this specific key
    key_usage_tracker[key] += 1
    current_usage = key_usage_tracker[key]

    # Log to the server console for observation
    print(f"[Mock API] Request received | Key: ...{key[-4:]} | Usage count: {current_usage}")

    # 3. Core logic: Rate limit trigger
    if current_usage <= 4:
        # First 7 times: Simulate a successful response from Google
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": f"This is a fake response from the Mock server. Key ending in: {key[-4:]}"}
                        ]
                    }
                }
            ]
        }
    else:
        # Trigger 429 Too Many Requests
        print(f"[Mock API] Key ...{key[-4:]} quota exceeded. Returning 429!")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": 429,
                    "message": "Quota exceeded for quota metric 'Generate requests'."
                }
            }
        )