from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.model import Asset, AlertRule,PriceSnapshot
from app.schemas.assets import AssetIds, AssetInDb
from fastapi import HTTPException, status
import httpx
from uuid import UUID

async def add_assets_service(asset_ids: AssetIds, db: AsyncSession):
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
                    "image": c["image"],
                    "current_price": c.get("current_price", 0.0)
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

async def get_user_tracked_assets(user_id: UUID, db: AsyncSession):
    stmt = select(Asset).join(AlertRule).where(AlertRule.user_id == user_id).distinct()
    result = await db.scalars(stmt)
    return result.all()


    