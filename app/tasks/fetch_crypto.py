from app.workers.celery_app import celery_app, redis as redis_client
from app.db.session import AsyncLocalSession
from app.models.model import Asset, PriceSnapshot, UserAsset
from sqlalchemy import select, delete
from sqlalchemy.sql import func
from celery import chain
import httpx
import orjson
import asyncio
from datetime import datetime, timedelta
import logging

# Setup logger
logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    name="fetch_popular_crypto_task",
    queue="simple_task_queue",
    ignore_result=True,
    autoretry_for=(httpx.HTTPError,), 
    retry_backoff=True, 
    retry_backoff_max=600, 
    max_retries=5, 
    rate_limit="1/m"
)
def fetch_popular_crypto(self):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 9,
        "page": 1
    }
    response = httpx.get(url, params=params, timeout=10.0)
    response.raise_for_status() 
    
    data = response.json()
    coins = [
        {
            "coingecko_id": c["id"], 
            "symbol": c["symbol"], 
            "name": c["name"],
            "image": c["image"],
            "current_price": c.get("current_price", 0.0)
        }
        for c in data
    ]
    print("check check check check check")
    redis_client.set("popular_coins", orjson.dumps(coins), ex=600)
    return "Success"
   

        

@celery_app.task(
    name="get_assets_prices",
    queue="heavy_task_queue"
                 )
def get_assets_prices():
    async def run():
        async with AsyncLocalSession() as db:
            result = await db.execute(select(Asset.coingecko_id))
            ids = result.scalars().all()

            if not ids:
                return {}

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": ",".join(ids), "vs_currencies": "usd"},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                return data

    return asyncio.run(run())

@celery_app.task(
    autoretry_for=(Exception,),
    queue="heavy_task_queue",
    ignore_result=True
)
def update_assets_price(price_data):
    """
    Update asset prices and create price snapshots.
    Implements 5-minute retention policy for snapshots.
    """
    if not price_data:
        logger.warning("⚠️ No price data to update")
        return "No data to update"

    async def run():
        async with AsyncLocalSession() as db:
            try:
                # Fetch assets from database
                result = await db.execute(
                    select(Asset).where(Asset.coingecko_id.in_(price_data.keys()))
                )
                assets = result.scalars().all()
                
                if len(assets) == 0:
                    logger.warning(f"⚠️ No assets found for IDs: {list(price_data.keys())}")
                    return "No assets found"
                
                logger.info(f"✅ Found {len(assets)} assets to update")
                
                assets_map = {a.coingecko_id: a for a in assets}
                snapshots_created = 0
                
                # Update prices and create snapshots
                for asset_id, value in price_data.items():
                    price = value.get("usd")
                    asset = assets_map.get(asset_id)
                    
                    if price is not None and asset:
                        # Update current price
                        old_price = asset.current_price
                        asset.current_price = price
                        
                        # Create price snapshot
                        snapshot = PriceSnapshot(asset_id=asset.id, price_usd=price)
                        db.add(snapshot)
                        snapshots_created += 1
                        
                        logger.info(f"💰 {asset.name}: ${old_price} → ${price}")
                
                # Commit the updates
                await db.commit()
                logger.info(f"✅ Committed {snapshots_created} price snapshots")
                
                # CLEANUP: Delete snapshots older than 5 minutes
                five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
                delete_stmt = delete(PriceSnapshot).where(
                    PriceSnapshot.timestamp < five_minutes_ago
                )
                result = await db.execute(delete_stmt)
                deleted_count = result.rowcount
                await db.commit()
                
                if deleted_count > 0:
                    logger.info(f"🧹 Deleted {deleted_count} old snapshots (older than 5 min)")
                
                # Cache the latest prices in Redis
                redis_client.set(
                    "asset:price:latest",
                    orjson.dumps(price_data),
                    ex=300  # 5 minutes
                )
                logger.info("💾 Cached latest prices in Redis")

                return f"Updated {snapshots_created} assets, deleted {deleted_count} old snapshots"
                
            except Exception as e:
                await db.rollback()
                logger.error(f"❌ Error updating prices: {e}", exc_info=True)
                raise e

    return asyncio.run(run())

@celery_app.task(name="update_assets_price_pipeline", queue="heavy_task_queue", ignore_result=True)
def update_assets_price_pipeline():
    chain_execution = (get_assets_prices.s() | update_assets_price.s())
    return chain_execution.apply_async()


@celery_app.task(
    name="cleanup_old_snapshots",
    queue="simple_task_queue",
    ignore_result=True
)
def cleanup_old_snapshots():
    """
    Standalone cleanup task to delete PriceSnapshots older than 5 minutes.
    Can be scheduled to run independently as a safety net.
    """
    async def run():
        async with AsyncLocalSession() as db:
            try:
                # Calculate cutoff time (5 minutes ago)
                five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
                
                # Count old snapshots before deletion
                count_stmt = select(func.count()).select_from(PriceSnapshot).where(
                    PriceSnapshot.timestamp < five_minutes_ago
                )
                count_result = await db.execute(count_stmt)
                old_count = count_result.scalar()
                
                if old_count == 0:
                    logger.info("✅ No old snapshots to clean up")
                    return "No old snapshots found"
                
                logger.info(f"🧹 Found {old_count} snapshots older than 5 minutes")
                
                # Delete old snapshots
                delete_stmt = delete(PriceSnapshot).where(
                    PriceSnapshot.timestamp < five_minutes_ago
                )
                result = await db.execute(delete_stmt)
                deleted_count = result.rowcount
                await db.commit()
                
                logger.info(f"✅ Deleted {deleted_count} old price snapshots")
                return f"Deleted {deleted_count} old snapshots"
                
            except Exception as e:
                await db.rollback()
                logger.error(f"❌ Error cleaning up snapshots: {e}", exc_info=True)
                raise e
    
    return asyncio.run(run())