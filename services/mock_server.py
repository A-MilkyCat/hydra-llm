from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import asyncio
from collections import defaultdict

app = FastAPI(title="Mock Gemini Server")

# Dictionaries to separately track successful usages and failed (rate-limited) attempts
success_tracker = defaultdict(int)
failure_tracker = defaultdict(int)

# Define the maximum allowed requests per API key
MAX_QUOTA = 7

@app.post("/v1beta/models/{model_name}:generateContent")
async def mock_gemini_endpoint(model_name: str, key: str = Query(None)):
    """
    Intercepts requests to simulate network latency and rate limits.
    Normal access takes 2 seconds. Exceeding the quota triggers an instant 429.
    """
    if not key:
        return JSONResponse(status_code=401, content={"error": "API key not valid."})

    # Core Logic: Determine behavior based on the current success count
    if success_tracker[key] < MAX_QUOTA:
        # 1. Normal Access: Increment success count and simulate AI processing time (2 seconds)
        success_tracker[key] += 1
        current_success = success_tracker[key]
        
        print(f"[Mock API] ✅ Success | Key: ...{key[-4:]} | Quota Used: {current_success}/{MAX_QUOTA}")
        
        await asyncio.sleep(2.0)
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": f"Fake response from Mock Server. Key ending in: {key[-4:]}"}
                        ]
                    }
                }
            ]
        }
    else:
        # 2. Rate Limit Triggered: Increment failure count and return 429 instantly
        failure_tracker[key] += 1
        current_failures = failure_tracker[key]
        
        # Display the specific number of invalid access attempts as requested
        print(f"[Mock API] ⚠️ Rate Limited (429) | Key: ...{key[-4:]} | Invalid access count: {current_failures}")
        
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": 429,
                    "message": "Quota exceeded for quota metric 'Generate requests'."
                }
            }
        )