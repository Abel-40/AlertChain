from app.workers.celery_app import celery_app
from datetime import timedelta

celery_app.conf.beat_schedule = {
    "fetch_popular_crypto_every_10minutes": {
        "task": "fetch_popular_crypto_task",
        "schedule": timedelta(minutes=9),
        "options": {
            "queue": "simple_task_queue",
            "priority": 9
        },
    }
}