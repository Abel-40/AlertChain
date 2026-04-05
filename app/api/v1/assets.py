from fastapi import APIRouter,Request, Depends,status,HTTPException
from app.api.dependencies import rate_limit,get_current_user
from app.schemas.responses import APIResponse
from app.utils.response import success_response
from app.schemas.assets import AssetOut,AssetInDb,AssetIds,AssetWithPrice
from app.models.model import User
from typing import List,Annotated
from pydantic import Field
from sqlalchemy import select
from app.models.model import Asset
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.db import get_db
from app.tasks.fetch_crypto import fetch_popular_crypto,get_assets_prices
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
    
    
@router.post("/add/")
async def add_assets(asset_ids: AssetIds, db: AsyncSession = Depends(get_db)):
    if not asset_ids.ids:
        return {"message": "No IDs provided"}

    stmt = select(Asset.coingecko_id).where(Asset.coingecko_id.in_(asset_ids.ids))
    result = await db.execute(stmt)
    existing_assets = result.scalars().all()
    assets_set = set(existing_assets)
    to_fetch = [id for id in asset_ids.ids if id not in assets_set]
    
    if not to_fetch:
        return {"message": "All assets are already registered!"}

    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ",".join(to_fetch) 
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url=url, params=params)
            response.raise_for_status()
            data = response.json()
            if not data:
                return {"message": "No matching assets found on CoinGecko"}

            new_assets = []
            for c in data:
                asset_data = {
                    "coingecko_id": c["id"], 
                    "symbol": c["symbol"], 
                    "name": c["name"],
                    "image": c["image"]
                }
                
                validated_data = AssetInDb(**asset_data).model_dump()
                new_assets.append(Asset(**validated_data))
            
            db.add_all(new_assets)
            await db.commit()
            
            return {"message": f"{len(new_assets)} assets registered successfully!!"}
        
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"External API error: {exc.response.text}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during asset registration"
        )
    
@router.get("/price/",response_model=APIResponse[List[AssetWithPrice]])    
async def get_asset_with_price(request:Request,current_user:User = Depends(get_current_user)):
    cache_key = "asset:price:latest"
    redis_client = request.app.state.redis
    cached = await redis_client.get(cache_key)
    if not cached:
        return success_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="no data yet. please try again later.",
            data=None
        )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="assets price fetched successfully!!",
        data=orjson.loads(cached)
    )
    
    