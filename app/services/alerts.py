from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.model import AlertRule, Asset, User
from app.schemas.alerts import CreateAlert
from fastapi import HTTPException, status
from uuid import UUID

async def create_alert_service(alert_data: CreateAlert, current_user: User, db: AsyncSession):
    stmt = select(Asset).where(Asset.coingecko_id == alert_data.asset_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="asset not found.")
    if asset.current_price is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset price not available yet")
        
    if alert_data.condition_type == "ABOVE":
        if alert_data.target_price <= asset.current_price:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target price must be greater than current price for ABOVE condition")
    elif alert_data.condition_type == "BELOW":
        if alert_data.target_price >= asset.current_price:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target price must be less than current price for BELOW condition")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid condition type")
        
    alert = AlertRule(user_id=current_user.id, asset_id=asset.id, target_price=alert_data.target_price, condition_type=alert_data.condition_type)
    db.add(alert)
    await db.commit()
    return alert

async def get_user_alerts(user_id: UUID, db: AsyncSession):
    stmt = select(AlertRule).where(AlertRule.user_id == user_id).order_by(AlertRule.updated_at.desc())
    result = await db.scalars(stmt)
    return result.all()

async def toggle_alert_status(alert_id: UUID, user_id: UUID, db: AsyncSession):
    stmt = select(AlertRule).where(AlertRule.id == alert_id, AlertRule.user_id == user_id)
    result = await db.scalars(stmt)
    alert = result.first()
    
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        
    alert.is_active = not alert.is_active
    await db.commit()
    await db.refresh(alert)
    return alert

async def delete_alert(alert_id: UUID, user_id: UUID, db: AsyncSession):
    stmt = select(AlertRule).where(AlertRule.id == alert_id, AlertRule.user_id == user_id)
    result = await db.scalars(stmt)
    alert = result.first()
    
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        
    await db.delete(alert)
    await db.commit()
    return True

async def bulk_delete_alerts(alert_ids: list[UUID], user_id: UUID, db: AsyncSession):
    stmt = delete(AlertRule).where(AlertRule.id.in_(alert_ids), AlertRule.user_id == user_id)
    result = await db.execute(stmt)
    await db.commit()
    return {"message": f"{result.rowcount} alerts deleted successfully"}
