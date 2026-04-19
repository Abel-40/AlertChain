from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user, rate_limit
from app.schemas.responses import APIResponse
from app.utils.response import success_response
from app.schemas.notifications import NotificationOut, NotificationBulkAction
from app.models.model import User
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.db import get_db
from uuid import UUID
from app.services.notifications import (
    get_user_notifications,
    get_unread_count,
    get_notification_by_id,
    mark_as_read,
    mark_all_as_read,
    bulk_mark_as_read,
    delete_notification,
    bulk_delete_notifications,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=APIResponse[List[NotificationOut]], dependencies=[Depends(rate_limit(limit=60, window=60))])
async def list_notifications(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    notifications = await get_user_notifications(user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message="Notifications retrieved successfully",
        data=[NotificationOut.model_validate(n) for n in notifications]
    )


@router.get("/{notification_id}", response_model=APIResponse[NotificationOut], dependencies=[Depends(rate_limit(limit=60, window=60))])
async def get_notification(notification_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    notification = await get_notification_by_id(notification_id=notification_id, user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message="Notification retrieved successfully",
        data=NotificationOut.model_validate(notification)
    )


@router.get("/unread-count", dependencies=[Depends(rate_limit(limit=120, window=60))])
async def unread_count(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    count = await get_unread_count(user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message="Unread count retrieved",
        data={"unread_count": count}
    )


@router.patch("/{notification_id}/read", response_model=APIResponse[NotificationOut], dependencies=[Depends(rate_limit(limit=60, window=60))])
async def mark_notification_read(notification_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    notification = await mark_as_read(notification_id=notification_id, user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message="Notification marked as read",
        data=NotificationOut.model_validate(notification)
    )


@router.patch("/read-all", dependencies=[Depends(rate_limit(limit=20, window=60))])
async def mark_all_notifications_read(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    count = await mark_all_as_read(user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message=f"{count} notifications marked as read",
        data={"updated_count": count}
    )


@router.patch("/bulk/read", dependencies=[Depends(rate_limit(limit=20, window=60))])
async def bulk_mark_notifications_read(payload: NotificationBulkAction, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    count = await bulk_mark_as_read(notification_ids=payload.notification_ids, user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message=f"{count} notifications marked as read",
        data={"updated_count": count}
    )


@router.delete("/{notification_id}", dependencies=[Depends(rate_limit(limit=40, window=60))])
async def delete_notification_endpoint(notification_id: UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await delete_notification(notification_id=notification_id, user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message="Notification deleted successfully",
        data=None
    )


@router.delete("/bulk/", dependencies=[Depends(rate_limit(limit=20, window=60))])
async def bulk_delete_notifications_endpoint(payload: NotificationBulkAction, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    count = await bulk_delete_notifications(notification_ids=payload.notification_ids, user_id=current_user.id, db=db)
    return success_response(
        status_code=200,
        message=f"{count} notifications deleted successfully",
        data={"deleted_count": count}
    )
