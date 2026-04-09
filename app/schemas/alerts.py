from pydantic import BaseModel, ConfigDict, model_validator
from uuid import UUID
from typing import Literal, Optional, List, Any
from datetime import datetime

class CreateAlert(BaseModel):
  asset_id: str          
  target_price: float
  condition_type: Literal["ABOVE", "BELOW"]

class AlertOut(BaseModel):
  id: UUID
  user_id: UUID
  asset_id: UUID
  asset_name: Optional[str] = None
  symbol: Optional[str] = None
  target_price: float
  condition_type: str
  is_active: bool
  last_triggered_at: Optional[datetime] = None
  updated_at: datetime
  created_at: Optional[datetime] = None

  model_config = ConfigDict(from_attributes=True)

  @model_validator(mode='before')
  @classmethod
  def populate_asset_fields(cls, data: Any) -> Any:
    """Pull asset_name and symbol from the related Asset ORM object."""
    if hasattr(data, 'asset') and data.asset is not None:
      asset = data.asset
      d = {
        'id': data.id,
        'user_id': data.user_id,
        'asset_id': data.asset_id,
        'asset_name': asset.name,
        'symbol': asset.symbol,
        'target_price': data.target_price,
        'condition_type': data.condition_type,
        'is_active': data.is_active,
        'last_triggered_at': data.last_triggered_at,
        'updated_at': data.updated_at,
        'created_at': getattr(data, 'created_at', None),
      }
      return d
    return data

class BulkDeleteAlerts(BaseModel):
    alert_ids: List[UUID]