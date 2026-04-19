from fastapi import APIRouter,Depends
from app.api.dependencies import get_current_user, rate_limit
from app.schemas.responses import APIResponse
from app.utils.response import success_response
from app.schemas.alerts import CreateAlert, AlertOut, BulkDeleteAlerts
from app.models.model import User
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.db import get_db
from uuid import UUID
from app.services.alerts import create_alert_service, get_user_alerts, toggle_alert_status, delete_alert, bulk_delete_alerts

router = APIRouter(prefix="/alert",tags=["alerts"])


@router.post("/create/", dependencies=[Depends(rate_limit(limit=20, window=60))])
async def create_alert(alert_data:CreateAlert,db:AsyncSession = Depends(get_db),current_user:User = Depends(get_current_user)):
  await create_alert_service(alert_data=alert_data, current_user=current_user, db=db)
  return {"message":"alert created successfully!!"}

@router.get("/", response_model=APIResponse[List[AlertOut]], dependencies=[Depends(rate_limit(limit=60, window=60))])
async def get_alerts_list(db:AsyncSession = Depends(get_db), current_user:User = Depends(get_current_user)):
    alerts = await get_user_alerts(user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message="Alerts retrieved successfully",
        data=[AlertOut.model_validate(a) for a in alerts]
    )

@router.patch("/{alert_id}/toggle", response_model=APIResponse[AlertOut], dependencies=[Depends(rate_limit(limit=40, window=60))])
async def toggle_alert(alert_id: UUID, db:AsyncSession = Depends(get_db), current_user:User = Depends(get_current_user)):
    alert = await toggle_alert_status(alert_id=alert_id, user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message="Alert status updated successfully",
        data=AlertOut.model_validate(alert)
    )

@router.delete("/{alert_id}", dependencies=[Depends(rate_limit(limit=40, window=60))])
async def delete_alert_endpoint(alert_id: UUID, db:AsyncSession = Depends(get_db), current_user:User = Depends(get_current_user)):
    await delete_alert(alert_id=alert_id, user_id=current_user.id, db=db)
    return {"message": "Alert deleted successfully"}

@router.delete("/bulk/", dependencies=[Depends(rate_limit(limit=20, window=60))])
async def bulk_delete_alerts_endpoint(payload: BulkDeleteAlerts, db:AsyncSession = Depends(get_db), current_user:User = Depends(get_current_user)):
    return await bulk_delete_alerts(alert_ids=payload.alert_ids, user_id=current_user.id, db=db)

