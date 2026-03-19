from fastapi import FastAPI,Request
from redis.asyncio import Redis
from contextlib import asynccontextmanager
from redis.exceptions import ConnectionError
from app.core.config import settings
from app.api.v1 import auth
@asynccontextmanager
async def lifespan(app:FastAPI):
  try:
    redis_client = Redis.from_url(settings.REDIS_FOR_CACHE,auto_close_connection_pool=True,max_connections=25)
    await redis_client.ping()
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
app.include_router(router=auth.router, prefix="/auth")
@app.get("/health/")
async def health():
  return {"server_health":"GOOD"}

@app.post("/set/")
async def set_data(request:Request,name:str):
  redis_client = request.app.state.redis
  await redis_client.set("name",name)
  return {"status":"okay"}


@app.get("/get_data/")
async def get_data(request:Request):
  redis_client = request.app.state.redis
  data = await redis_client.get("name")
  return {"name":data}