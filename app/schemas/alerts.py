from pydantic import BaseModel
from uuid import UUID
from typing import Literal

class CreateAlert(BaseModel):
  asset_coingecko_id:str
  target_price:float
  condition_type:Literal["ABOVE", "BELOW"]
  