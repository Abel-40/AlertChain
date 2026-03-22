from celery import Celery
from app.core.config import settings
from kombu import Queue
from fastapi_mail import MessageSchema,FastMail,MessageType
from app.core.email_config import conf
import socket
import asyncio
celery_app = Celery(broker=settings.REDIS_FOR_BROKER,backend=settings.REDIS_FOR_BACKEND)

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

@celery_app.task
def check_smtp_task():
    try:
        with socket.create_connection(("smtp.gmail.com", 587), timeout=5):
            return "SMTP reachable"
    except Exception as e:
        return f"SMTP not reachable: {e}"

@celery_app.task(bind=True,autoretry_for = (Exception,),retry_backoff=True,retry_backoff_max=600,max_retries=5)
def send_email(self,email:str,name:str):
  async def send():
    message = MessageSchema(
      subject="Welcome to crypto mate",
      recipients=[email],
      template_body={"name":name},
      subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message=message,template_name="welcome.html")
    
  asyncio.run(send())
  