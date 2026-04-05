from app.workers.celery_app import celery_app, redis as redis_client
from app.db.session import AsyncLocalSession
from app.workers.celery_app import celery_app,redis as redis_client
from app.models.model import Asset,PriceSnapshot
from sqlalchemy import select
from celery import chain
import httpx
import orjson
import asyncio
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
        {"coingecko_id": c["id"], "symbol": c["symbol"], "name": c["name"],"image":c["image"]}
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
    if not price_data:
        return "No data to update"

    async def run():
        async with AsyncLocalSession() as db:
            result = await db.execute(
                select(Asset).where(Asset.coingecko_id.in_(price_data.keys()))
            )
            assets_map = {a.coingecko_id: a for a in result.scalars().all()}

            for asset_id, value in price_data.items():
                price = value.get("usd")
                asset = assets_map.get(asset_id)
                if price is not None and asset:
                    asset.current_price = price
                    db.add(PriceSnapshot(asset_id=asset.id, price_usd=price))

            await db.commit()
   
        redis_client.set(
            "asset:price:latest",
            orjson.dumps(price_data),
            ex=300
        )
        return "done"

    return asyncio.run(run())

@celery_app.task(name="update_assets_price_pipeline", ignore_result=True)
def update_assets_price_pipeline():
    chain_execution = (get_assets_prices.s() | update_assets_price.s())
    return chain_execution.apply_async()