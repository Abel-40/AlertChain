from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional, Literal
from datetime import datetime


class NotificationOut(BaseModel):
    id: UUID
    user_id: UUID
    alert_rule_id: UUID
    message: str
    status: Literal["PENDING", "SENT", "FAILED"]
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationBulkAction(BaseModel):
    notification_ids: list[UUID]
