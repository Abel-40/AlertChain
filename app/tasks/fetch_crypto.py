from app.workers.celery_app import celery_app
import httpx
import orjson
from app.workers.celery_app import celery_app,redis as redis_client
import httpx
import orjson
import httpx
import orjson
from app.workers.celery_app import celery_app, redis as redis_client

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
        
