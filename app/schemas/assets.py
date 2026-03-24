from pydantic import BaseModel,ConfigDict

class AssetOut(BaseModel):
  id:str
  symbol:str
  name:str
  model_config = ConfigDict(from_attributes=True)
  