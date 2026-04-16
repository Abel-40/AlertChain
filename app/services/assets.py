from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.model import Asset, AlertRule, PriceSnapshot, UserAsset
from app.schemas.assets import AssetIds, AssetInDb
from fastapi import HTTPException, status
import httpx
from uuid import UUID

async def add_assets_service(asset_ids: AssetIds, db: AsyncSession, user_id: UUID = None):
    """
    Add assets to user's watchlist using junction table.
    Creates global asset if it doesn't exist, then links to user.
    """
    if not asset_ids.ids:
        return {"message": "No IDs provided", "added_count": 0}

    # Step 1: Find or create assets in global Asset table
    stmt = select(Asset.coingecko_id).where(Asset.coingecko_id.in_(asset_ids.ids))
    result = await db.execute(stmt)
    existing_assets = result.scalars().all()
    assets_set = set(existing_assets)
    to_fetch = [id for id in asset_ids.ids if id not in assets_set]
    
    # Fetch missing assets from CoinGecko
    if to_fetch:
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
                    return {"message": "No matching assets found on CoinGecko", "added_count": 0}

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
                await db.flush()  # Flush to get IDs without committing
                
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
    
    # Step 2: Link assets to user via junction table
    if not user_id:
        return {"message": "User ID is required", "added_count": 0}
    
    # Get all asset IDs (both existing and newly created)
    all_assets_stmt = select(Asset).where(Asset.coingecko_id.in_(asset_ids.ids))
    all_assets_result = await db.execute(all_assets_stmt)
    all_assets = all_assets_result.scalars().all()
    
    added_count = 0
    for asset in all_assets:
        # Check if user already has this asset
        existing_link = await db.execute(
            select(UserAsset).where(
                UserAsset.user_id == user_id,
                UserAsset.asset_id == asset.id
            )
        )
        
        if not existing_link.scalar_one_or_none():
            # Create junction table entry
            user_asset = UserAsset(
                user_id=user_id,
                asset_id=asset.id
            )
            db.add(user_asset)
            added_count += 1
    
    await db.commit()
    
    return {"message": f"{added_count} assets added to your watchlist", "added_count": added_count}

async def get_user_tracked_assets(user_id: UUID, db: AsyncSession):
    """Get all assets tracked by a specific user via junction table"""
    stmt = (
        select(Asset)
        .join(UserAsset, Asset.id == UserAsset.asset_id)
        .where(UserAsset.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def remove_asset_from_user(user_id: UUID, coingecko_id: str, db: AsyncSession) -> bool:
    """
    Remove asset from user's watchlist by deleting junction table entry.
    Does NOT delete the asset from global Asset table.
    """
    # Find asset by coingecko_id
    asset_stmt = select(Asset).where(Asset.coingecko_id == coingecko_id)
    asset_result = await db.execute(asset_stmt)
    asset = asset_result.scalar_one_or_none()
    
    if not asset:
        return False
    
    # Delete junction table entry
    from sqlalchemy import delete
    delete_stmt = delete(UserAsset).where(
        UserAsset.user_id == user_id,
        UserAsset.asset_id == asset.id
    )
    
    result = await db.execute(delete_stmt)
    await db.commit()
    
    return result.rowcount > 0


    