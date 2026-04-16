from fastapi import APIRouter, Request, Depends, status, HTTPException, Query
from app.api.dependencies import rate_limit, get_current_user
from app.schemas.responses import APIResponse, PaginatedResponse, QueryParams
from app.utils.response import success_response, paginated_query
from app.schemas.assets import AssetOutFromSearch, AssetInDb, AssetIds, PriceSnapshotOut, AssetOutFromDb
from app.models.model import User, PriceSnapshot, Asset, AlertRule
from uuid import UUID
from typing import List, Annotated
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.db import get_db
from app.tasks.fetch_crypto import fetch_popular_crypto
import orjson
import httpx
from app.services.assets import add_assets_service, get_user_tracked_assets, remove_asset_from_user

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/popular", response_model=APIResponse[List[AssetOutFromSearch]], dependencies=[Depends(rate_limit(limit=30, window=60))])
async def get_popular_assets(request: Request):
    redis = request.app.state.redis
    cached_data = await redis.get("popular_coins")

    if not cached_data:
        fetch_popular_crypto.delay()
        return success_response(status_code=200, message="No cached data yet, try again", data=[])

    try:
        popular_coins = orjson.loads(cached_data)
    except Exception:
        fetch_popular_crypto.delay()
        return success_response(status_code=200, message="Cache corrupted, refreshing", data=[])

    return success_response(status_code=200, message="Fetched successfully", data=popular_coins)


@router.get("/search", response_model=APIResponse[List[AssetOutFromSearch]], dependencies=[Depends(rate_limit(limit=20, window=60))])
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
            response = await client.get(url, params={"query": crypto_name}, timeout=15.0)
            response.raise_for_status()
            raw_data = response.json()
            coins = [AssetOutFromSearch.from_search_result(coin).model_dump() for coin in raw_data.get("coins", [])]
            await redis_client.set(cache_key, orjson.dumps(coins), ex=600)
            return success_response(
                status_code=status.HTTP_200_OK,
                message="Search results fetched successfully",
                data=coins
            )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"External API error: {exc.response.text}")
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during search")


@router.post("/add/", dependencies=[Depends(rate_limit(limit=10, window=60))])
async def add_assets(
    asset_ids: AssetIds, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add assets to current user's watchlist"""
    return await add_assets_service(asset_ids=asset_ids, db=db, user_id=current_user.id)


@router.get("/tracked", response_model=APIResponse[List[AssetOutFromDb]], dependencies=[Depends(rate_limit(limit=30, window=60))])
async def get_tracked_assets_endpoint(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    assets = await get_user_tracked_assets(user_id=current_user.id, db=db)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Tracked assets retrieved successfully",
        data=[AssetOutFromDb.model_validate(asset) for asset in assets]
    )


@router.delete("/tracked/{coingecko_id}", dependencies=[Depends(rate_limit(limit=20, window=60))])
async def remove_tracked_asset(
    coingecko_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove an asset from the user's watchlist by deleting junction table entry."""
    success = await remove_asset_from_user(
        user_id=current_user.id,
        coingecko_id=coingecko_id,
        db=db
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Asset not found in your watchlist"
        )
    
    return success_response(
        status_code=status.HTTP_200_OK,
        message=f"Removed asset {coingecko_id} from your watchlist",
        data={"removed": True}
    )


@router.get("/price/", dependencies=[Depends(rate_limit(limit=60, window=60))])
async def get_asset_with_price(request: Request, current_user: User = Depends(get_current_user)):
    cache_key = "asset:price:latest"
    redis_client = request.app.state.redis
    cached = await redis_client.get(cache_key)
    if not cached:
        return success_response(
            status_code=status.HTTP_200_OK,
            message="No data yet. Please try again later.",
            data=[]
        )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Assets price fetched successfully",
        data=orjson.loads(cached)
    )


@router.get("/detail/{coingecko_id}", response_model=APIResponse[AssetOutFromDb], dependencies=[Depends(rate_limit(limit=60, window=60))])
async def get_asset_by_id(
    coingecko_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single asset by its coingecko_id"""
    print(f"🔍 Fetching asset detail for: {coingecko_id}")
    stmt = select(Asset).where(Asset.coingecko_id == coingecko_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    
    if not asset:
        print(f"❌ Asset not found: {coingecko_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset '{coingecko_id}' not found in database. Please add it first.")
    
    print(f"✅ Asset found: {asset.name}")
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Asset fetched successfully",
        data=AssetOutFromDb.model_validate(asset)
    )


@router.get("/price/snapshot/{coingecko_id}", dependencies=[Depends(rate_limit(limit=30, window=60))])
async def get_asset_price_snapshot(
    q: Annotated[QueryParams, Query()],
    coingecko_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get asset by coingecko_id first
    asset_stmt = select(Asset).where(Asset.coingecko_id == coingecko_id)
    asset_result = await db.execute(asset_stmt)
    asset = asset_result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    
    price_snapshots = await paginated_query(
        db,
        select(PriceSnapshot).where(PriceSnapshot.asset_id == asset.id).order_by(PriceSnapshot.timestamp.desc()),
        q.page,
        q.page_size
    )
    return success_response(
        message="Price snapshot fetched successfully",
        data={
            "items": [PriceSnapshotOut.model_validate(i) for i in price_snapshots["items"]],
            "pagination": price_snapshots["meta"]
        },
        status_code=status.HTTP_200_OK
    )