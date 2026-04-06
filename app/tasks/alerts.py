from fastapi_mail import FastMail,MessageSchema, MessageType
from app.core.email_config import conf
from app.workers.celery_app import celery_app, redis as redis_client
from app.db.session import AsyncLocalSession
from app.models.model import AlertRule,Notification
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from celery import chain
from typing import List,Dict,Any
from pydantic import EmailStr
from datetime import datetime, timedelta
import httpx
import orjson
import asyncio
import socket

@celery_app.task(queue="simple_task_queue")
def check_smtp_task():
    try:
        with socket.create_connection(("smtp.gmail.com", 587), timeout=5):
            return "SMTP reachable"
    except Exception as e:
        return f"SMTP not reachable: {e}"
   
async def email_sender(subject:str,recipients:List[EmailStr],template_body_vars:Dict[str,Any],template_file_name:str):
    message = MessageSchema(
    subject=subject,
    recipients=recipients,
    template_body=template_body_vars,
    subtype=MessageType.html
  )
    fm = FastMail(conf)
    
    print("EMAIL IS SENDING INPROGRESS")
    await fm.send_message(message=message,template_name=template_file_name)
    print("EMAIL IS SENDED")  
    
@celery_app.task(bind=True,autoretry_for = (Exception,),retry_backoff=True,retry_backoff_max=600,max_retries=None,queue="simple_task_queue")
def send_email(self,email:str,name:str):
  asyncio.run(email_sender(subject="Welcome to AlertChain",recipients=[email],template_body_vars={"name":name,"dashboard_url":"http://127.0.0.0:3000/dashboard"},template_file_name="welcome.html"))

@celery_app.task(bind=True,autoretry_for = (Exception,),retry_backoff=True,retry_backoff_max=600,max_retries=None,queue="simple_task_queue")
def send_email_forget_password(self,reset_link:str,email:str):
    asyncio.run(email_sender(subject="AlertChain Password Reset",recipients=[email],template_body_vars={"reset_link":reset_link},template_file_name="passreset.html"))



COOLDOWN_SECONDS = 300
@celery_app.task(
    name="alert_checker",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
    queue="heavy_task_queue",
    ignore_result=True
)
def alert_checker():
    async def run():
        async with AsyncLocalSession() as db:
            stmt = select(AlertRule).options(
                selectinload(AlertRule.user),
                selectinload(AlertRule.asset)
            ).where(AlertRule.is_active == True)
            result = await db.scalars(stmt)
            alerts = result.all()

            if not alerts:
                return []

            cached = redis_client.get("asset:price:latest")
            if not cached:
                return []

            assets_price = orjson.loads(cached)

            triggered_alerts = []

            for alert in alerts:
                if alert.last_triggered_at:
                    if datetime.utcnow() - alert.last_triggered_at < timedelta(seconds=COOLDOWN_SECONDS):
                        continue

                asset_data = assets_price.get(alert.asset.coingecko_id)
                if not asset_data:
                    continue

                asset_price = asset_data["usd"]

                triggered = (
                    alert.condition_type == "ABOVE" and asset_price >= alert.target_price
                ) or (
                    alert.condition_type == "BELOW" and asset_price <= alert.target_price
                )

                if triggered:
                    print("|------ THERE IS FULLFILED  ALERT RULE!!! ------|")
                    triggered_alerts.append({
                        "alert_rule_id": str(alert.id),
                        "user_id": str(alert.user_id),
                        "email": alert.user.email,
                        "name": alert.user.full_name,
                        "asset_id": alert.asset.coingecko_id,
                        "price": asset_price,
                        "target_price": alert.target_price,
                        "condition": alert.condition_type
                    })

            return triggered_alerts

    alerts = asyncio.run(run())

    for alert in alerts:
        notification_sender.delay(alert)

    return f"{len(alerts)} alerts triggered"

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
    queue="simple_task_queue",
    ignore_result=True
)
def notification_sender(self, alert_data):
    async def run():
        async with AsyncLocalSession() as db:

            try:
                
                await email_sender(
                    subject=f"{alert_data['asset_id']} Price Alert",
                    recipients=[alert_data["email"]],
                    template_body_vars={
                        "name": alert_data["name"],
                        "asset": alert_data["asset_id"],
                        "price": alert_data["price"],
                        "target_price": alert_data["target_price"],
                        "condition": alert_data["condition"],
                    },
                    template_file_name="price_alert.html"
                )

                notification = Notification(
                    user_id=alert_data["user_id"],
                    alert_rule_id=alert_data["alert_rule_id"],
                    message=f"{alert_data['asset_id']} is {alert_data['price']} ({alert_data['condition']} {alert_data['target_price']})",
                    status="SENT"
                )
                db.add(notification)

                alert = await db.get(AlertRule, alert_data["alert_rule_id"])
                if alert:
                    alert.last_triggered_at = datetime.utcnow()
                    print(f"|------ ALERT FOR {alert_data['asset_id']} SENDED!!! -------|")
                await db.commit()

            except Exception as e:
                await db.rollback()

                notification = Notification(
                    user_id=alert_data["user_id"],
                    alert_rule_id=alert_data["alert_rule_id"],
                    message=str(e),
                    status="FAILED"
                )
                db.add(notification)
                print(f"|------ ALERT FOR {alert_data['asset_id']} FAILED!!! -------|")
                await db.commit()

                raise e

    asyncio.run(run())

    