from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Literal, Optional, List
from datetime import datetime

class CreateAlert(BaseModel):
  asset_coingecko_id:str
  target_price:float
  condition_type:Literal["ABOVE", "BELOW"]

class AlertOut(BaseModel):
  id: UUID
  user_id: UUID
  target_price: float
  condition_type: str
  is_active: bool
  last_triggered_at: Optional[datetime]
  updated_at: datetime
  asset_id: UUID
  
  model_config = ConfigDict(from_attributes=True)
  
class BulkDeleteAlerts(BaseModel):
    alert_ids: List[UUID]
  