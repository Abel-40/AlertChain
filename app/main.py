from fastapi import FastAPI,Request, HTTPException
from redis.asyncio import Redis
from contextlib import asynccontextmanager
from redis.exceptions import ConnectionError
from app.core.config import settings
from app.api.v1 import auth,assets,alerts,notifications
from app.utils.response import error_response
from fastapi.exceptions import RequestValidationError
Rate_Limit_Script = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local limit = tonumber(ARGV[4])
local request_id = ARGV[5]

redis.call("zremrangebyscore", key, 0, window_start)
local counter = redis.call("zcard", key)

if counter >= limit then
  return 0
end

redis.call("zadd", key, now, request_id)
redis.call("expire", key, window)
return 1
"""

@asynccontextmanager
async def lifespan(app:FastAPI):
  try:
    redis_client = Redis.from_url(settings.REDIS_FOR_CACHE,auto_close_connection_pool=True,max_connections=25)
    await redis_client.ping()
    app.state.rate_limit_script = redis_client.register_script(Rate_Limit_Script)
    app.state.redis = redis_client
    print("Successfully connected to Redis")
    
    yield
    
  except ConnectionError as e:
    print(f"Redis connection error: {e}")
    raise RuntimeError(f"Could not connect to Redis: {e}")
  finally:
    if hasattr(app.state,"redis"):
      await app.state.redis.aclose()
      print("Redis connection closed")
    
app = FastAPI(lifespan=lifespan)
app.include_router(router=auth.router, prefix="/alertchain")
app.include_router(router=assets.router,prefix="/alertchain")
app.include_router(router=alerts.router,prefix="/alertchain")
app.include_router(router=notifications.router,prefix="/alertchain")

@app.exception_handler(HTTPException)
def http_exception_handler(request:Request,exc:HTTPException):
  return error_response(status_code=exc.status_code,message=exc.detail)

@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError):
    field_errors = {}
    for err in exc.errors():
        location = err["loc"][-1]
        field = str(location) 
        
        field_errors.setdefault(field, []).append(err["msg"])
        
    return error_response(
        status_code=422, 
        message="Invalid request data", 
        errors=field_errors
    )

@app.exception_handler(Exception)
def general_exception_handler(request:Request,exc:Exception):
  return error_response(status_code=500,message="Something went wrong please try again later!!!")


@app.get("/health/")
async def health():
  return {"server_health":"GOOD"}