from celery import Celery
from app.core.config import settings
from kombu import Queue
from redis import Redis


celery_app = Celery(
                    broker=settings.REDIS_FOR_BROKER,
                    backend=settings.REDIS_FOR_BACKEND, 
                    
                    )
celery_app.autodiscover_tasks(["app"])
redis = Redis.from_url(settings.REDIS_FOR_CACHE, max_connections=10)

import app.workers.beat

celery_app.conf.update(
  task_serializer = "json",
  result_serializer = "json",
  accept_content = ["json"],
  timezone = "UTC",
  enable_utc = True,
  task_track_started = True,
  result_expires = 3600
)

celery_app.task_queues = (
  Queue(name="simple_task_queue",queue_arguments={"x-max-priority":10}),
  Queue(name="heavy_task_queue",queue_arguments={"x-max-priority":30})
)




  