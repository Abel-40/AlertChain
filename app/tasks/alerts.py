from fastapi_mail import FastMail,MessageSchema, MessageType
from app.core.email_config import conf
from app.workers.celery_app import celery_app
import asyncio
import socket

@celery_app.task
def check_smtp_task():
    try:
        with socket.create_connection(("smtp.gmail.com", 587), timeout=5):
            return "SMTP reachable"
    except Exception as e:
        return f"SMTP not reachable: {e}"
   
      
@celery_app.task(bind=True,autoretry_for = (Exception,),retry_backoff=True,retry_backoff_max=600,max_retries=None,queue="simple_task_queue")
def send_email(self,email:str,name:str):
  async def send():
    message = MessageSchema(
      subject="Welcome to crypto mate",
      recipients=[email],
      template_body={"name":name,"dashboard_url":"http://127.0.0.0:3000/dashboard"},
      subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message=message,template_name="welcome.html")
    
  asyncio.run(send())
  