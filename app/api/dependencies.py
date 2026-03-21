from fastapi import Request, HTTPException,status
import uuid
import time

def rate_limit(limit: int, window: int):
  async def actual_dependency(request: Request):
    
    client_ip = request.client.host
    key = f"throttle:{client_ip}"
    
    now = time.time()
    window_start = now - window
    request_id = str(uuid.uuid4())
    script_obj = request.app.state.rate_limit_script
    result = await script_obj(
        keys=[key], 
        args=[window_start, window, now, limit, request_id]
    )

    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
            detail="Rate limit exceeded. Try again later."
        )
  return actual_dependency
  