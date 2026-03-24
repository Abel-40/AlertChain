from fastapi import APIRouter,Request, Depends,status
from app.api.dependencies import rate_limit,get_current_user
from app.schemas.responses import APIResponse
from app.utils.response import success_response
from app.schemas.assets import AssetOut
from typing import List
from app.tasks.fetch_crypto import fetch_popular_crypto
import orjson
router = APIRouter(prefix="/assets",tags=["assets"])
  
@router.get("/popular", response_model=APIResponse[List[AssetOut]])
async def get_popular_assets(request: Request):
    redis = request.app.state.redis

    cached_data = await redis.get("popular_coins")

    if not cached_data:
        fetch_popular_crypto.delay()
        return success_response(
            status_code=200,
            message="No cached data yet, try again",
            data=[]
        )

    try:
        popular_coins = orjson.loads(cached_data)
    except Exception:
        fetch_popular_crypto.delay()
        return success_response(
            status_code=200,
            message="Cache corrupted, refreshing",
            data=[]
        )

    return success_response(
        status_code=200,
        message="fetched_successfully!!",
        data=popular_coins
    )