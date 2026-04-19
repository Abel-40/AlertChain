from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from app.models.model import Notification
from fastapi import HTTPException, status
from uuid import UUID


async def get_notification_by_id(notification_id: UUID, user_id: UUID, db: AsyncSession):
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user_id
    )
    result = await db.scalars(stmt)
    notification = result.first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    return notification


async def get_user_notifications(user_id: UUID, db: AsyncSession):
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    result = await db.scalars(stmt)
    return result.all()


async def get_unread_count(user_id: UUID, db: AsyncSession) -> int:
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def mark_as_read(notification_id: UUID, user_id: UUID, db: AsyncSession):
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user_id
    )
    result = await db.scalars(stmt)
    notification = result.first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


async def mark_all_as_read(user_id: UUID, db: AsyncSession) -> int:
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def bulk_mark_as_read(notification_ids: list[UUID], user_id: UUID, db: AsyncSession) -> int:
    stmt = (
        update(Notification)
        .where(
            Notification.id.in_(notification_ids),
            Notification.user_id == user_id
        )
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def delete_notification(notification_id: UUID, user_id: UUID, db: AsyncSession):
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user_id
    )
    result = await db.scalars(stmt)
    notification = result.first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    await db.delete(notification)
    await db.commit()
    return True


async def bulk_delete_notifications(notification_ids: list[UUID], user_id: UUID, db: AsyncSession) -> int:
    stmt = (
        delete(Notification)
        .where(
            Notification.id.in_(notification_ids),
            Notification.user_id == user_id
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
