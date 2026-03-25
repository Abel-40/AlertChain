from fastapi import APIRouter,Request, Depends,status,HTTPException
from app.api.dependencies import rate_limit,get_current_user
from app.schemas.responses import APIResponse
from app.utils.response import success_response
from app.schemas.assets import AssetOut
from typing import List
from app.tasks.fetch_crypto import fetch_popular_crypto
import orjson
import httpx
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
    
    
@router.get("/search", response_model=APIResponse[List[AssetOut]])
async def search_crypto(crypto_name: str, request: Request):
    cache_key = f"search:{crypto_name.lower()}"
    redis_client = request.app.state.redis

    cached = await redis_client.get(cache_key)
    if cached:
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Search results fetched from cache",
            data=orjson.loads(cached)
        )
    try:
        url = "https://api.coingecko.com/api/v3/search"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"query": crypto_name}, timeout=10.0)
            response.raise_for_status()
            
            raw_data = response.json()
  
            coins = [AssetOut(**coin).model_dump() for coin in raw_data.get("coins", [])]
            
            await redis_client.set(cache_key, orjson.dumps(coins), ex=600)
            
            return success_response(
                status_code=status.HTTP_200_OK,
                message="Search results fetched successfully",
                data=coins
            )

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"External API error: {exc.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during search"
        )
    