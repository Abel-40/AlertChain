from app.workers.celery_app import celery_app, redis as redis_client
from app.db.session import AsyncLocalSession
from app.models.model import Asset, PriceSnapshot, UserAsset
from sqlalchemy import select, delete
from sqlalchemy.sql import func
from celery import chain
import httpx
import orjson
import asyncio
from datetime import datetime, timedelta, timezone
import logging

# Setup logger
logger = logging.getLogger(__name__)
CACHE_TTL = 86400
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
    name="fetch_coin_details",
    queue="heavy_task_queue",
    bind=True
)
def fetch_coin_details(self, coingecko_id: str):
    """
    Fetch detailed coin data from CoinGecko and store in Redis
    
    Args:
        coingecko_id: CoinGecko coin ID (e.g., 'bitcoin', 'ethereum')
    """
    async def run():
        redis_key = f"asset:details:{coingecko_id}"
        
        try:
            # Fetch data from CoinGecko
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.coingecko.com/api/v3/coins/{coingecko_id}",
                    params={
                        "tickers": "false",
                        "community_data": "true",
                        "developer_data": "true",
                        "sparkline": "false"
                    },
                    timeout=15.0
                )
                response.raise_for_status()
                raw_data = response.json()
            
            # Extract and structure the data (without current_price and development)
            coin_detail = {
                "header": {
                    "name": raw_data["name"],
                    "symbol": raw_data["symbol"].upper(),
                    "image": raw_data["image"]["large"],
                    "rank": raw_data["market_cap_rank"]
                },
                
                "price_panel": {
                    "changes": {
                        "1h": raw_data["market_data"]["price_change_percentage_1h_in_currency"]["usd"],
                        "24h": raw_data["market_data"]["price_change_percentage_24h"],
                        "7d": raw_data["market_data"]["price_change_percentage_7d"],
                        "14d": raw_data["market_data"]["price_change_percentage_14d"],
                        "30d": raw_data["market_data"]["price_change_percentage_30d"],
                        "1y": raw_data["market_data"]["price_change_percentage_1y"]
                    },
                    "high_24h": raw_data["market_data"]["high_24h"]["usd"],
                    "low_24h": raw_data["market_data"]["low_24h"]["usd"]
                },
                
                "market_stats": {
                    "market_cap": raw_data["market_data"]["market_cap"]["usd"],
                    "fdv": raw_data["market_data"]["fully_diluted_valuation"]["usd"],
                    "volume_24h": raw_data["market_data"]["total_volume"]["usd"],
                    "circulating_supply": raw_data["market_data"]["circulating_supply"],
                    "total_supply": raw_data["market_data"]["total_supply"],
                    "max_supply": raw_data["market_data"]["max_supply"]
                },
                
                "historical_highlights": {
                    "ath": {
                        "price": raw_data["market_data"]["ath"]["usd"],
                        "date": raw_data["market_data"]["ath_date"]["usd"],
                        "change_percentage": raw_data["market_data"]["ath_change_percentage"]["usd"]
                    },
                    "atl": {
                        "price": raw_data["market_data"]["atl"]["usd"],
                        "date": raw_data["market_data"]["atl_date"]["usd"],
                        "change_percentage": raw_data["market_data"]["atl_change_percentage"]["usd"]
                    }
                },
                
                "about": {
                    "description": raw_data["description"]["en"],
                    "genesis": raw_data.get("genesis_date"),
                    "algorithm": raw_data.get("hashing_algorithm"),
                    "categories": raw_data["categories"]
                },
                
                "links": {
                    "homepage": raw_data["links"]["homepage"][0] if raw_data["links"]["homepage"] else None,
                    "whitepaper": raw_data["links"].get("whitepaper"),
                    "blockchain_site": raw_data["links"]["blockchain_site"][0] if raw_data["links"]["blockchain_site"] else None,
                    "subreddit": raw_data["links"]["subreddit_url"],
                    "twitter": f"https://twitter.com/{raw_data['links']['twitter_screen_name']}" if raw_data["links"]["twitter_screen_name"] else None,
                    "github": raw_data["links"]["repos_url"]["github"][0] if raw_data["links"]["repos_url"]["github"] else None,
                    "official_forum": raw_data["links"]["official_forum_url"][0] if raw_data["links"]["official_forum_url"] else None
                },
                
                "community": {
                    "reddit_subscribers": raw_data["community_data"]["reddit_subscribers"],
                    "sentiment_up_percentage": raw_data["sentiment_votes_up_percentage"],
                    "sentiment_down_percentage": raw_data["sentiment_votes_down_percentage"],
                    "watchlist_users": raw_data["watchlist_portfolio_users"]
                }
            }
            
            # Store in Redis with 24h TTL
            redis_client.setex(
                redis_key,
                CACHE_TTL,
                orjson.dumps(coin_detail)
            )
            
            return coin_detail
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error {e.response.status_code} for {coingecko_id}: {e}"
            logger.error(f"❌ Error fetching {coingecko_id}: {error_msg}", exc_info=True)
            return None
        except Exception as e:
            error_msg = f"Error fetching {coingecko_id}: {str(e)}"
            logger.error(f"❌ Error fetching {coingecko_id}: {error_msg}", exc_info=True)
            return None
    
    return asyncio.run(run())


@celery_app.task(
    name="fetch_historical_price_snapshots",
    queue="heavy_task_queue",
    bind=True
)
def fetch_historical_price_snapshots(self, coingecko_id: str, duration: float = 1.0):
    """
    Fetch historical price snapshots from CoinGecko market_chart API and store in Redis.
    
    Args:
        coingecko_id: CoinGecko coin ID (e.g., 'bitcoin', 'ethereum')
        duration: Duration in days (0.04 for ~1 hour, 1 for 24h with 5-min intervals, 2-90 for hourly)
    
    Returns:
        Number of price points cached
    """
    async def run():
        async with AsyncLocalSession() as db:
            try:
                logger.info(f"📊 Fetching historical data for {coingecko_id} (duration: {duration} days)")
                
                # Fetch asset from database
                asset_stmt = select(Asset).where(Asset.coingecko_id == coingecko_id)
                asset_result = await db.execute(asset_stmt)
                asset = asset_result.scalar_one_or_none()
                
                if not asset:
                    logger.error(f"❌ Asset {coingecko_id} not found in database")
                    return f"Asset {coingecko_id} not found"
                
                # Fetch market chart data from CoinGecko
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart",
                        params={
                            "vs_currency": "usd",
                            "days": duration
                        },
                        timeout=30.0
                    )
                    response.raise_for_status()
                    data = response.json()
                
                prices = data.get("prices", [])
                logger.info(f"✅ Fetched {len(prices)} price points from CoinGecko")
                
                if not prices:
                    logger.warning(f"⚠️ No price data returned for {coingecko_id}")
                    return "No price data from CoinGecko"

                # Convert price data to serializable format
                price_data = []
                for price_point in prices:
                    price_data.append({
                        "timestamp": datetime.fromtimestamp(price_point[0] / 1000, tz=timezone.utc).isoformat(),
                        "price_usd": price_point[1]
                    })
                
                # Store in Redis with cache key including duration
                cache_key = f"asset:historical:{coingecko_id}:{duration}"
                cache_ttl = int(duration * 3600)  # TTL based on duration (1 day = 3600 seconds)
                # Minimum 5 minutes, maximum 24 hours
                cache_ttl = max(300, min(cache_ttl, 86400))
                
                redis_client.set(cache_key, orjson.dumps(price_data), ex=cache_ttl)
                logger.info(f"💾 Cached {len(price_data)} price points for {duration} days (TTL: {cache_ttl}s)")
                
                # Update asset's current price with latest price
                if price_data:
                    latest_price = price_data[-1]["price_usd"]
                    asset.current_price = latest_price
                    await db.commit()
                    logger.info(f"💰 Updated {coingecko_id} current price to ${latest_price}")
                
                return len(price_data)
                
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ HTTP error fetching {coingecko_id}: {e.response.status_code} - {e.response.text}", exc_info=True)
                return f"HTTP error: {e.response.status_code}"
            except Exception as e:
                logger.error(f"❌ Error fetching historical data for {coingecko_id}: {e}", exc_info=True)
                raise e
    
    return asyncio.run(run())


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