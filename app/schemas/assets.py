from pydantic import BaseModel,ConfigDict,Field, field_validator,AliasChoices
from uuid import UUID
from typing import List,Optional, Dict, Any
from datetime import datetime


from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class AssetOut(BaseModel):
    coingecko_id: Optional[str] = Field(default=None, validation_alias=AliasChoices('id', 'coingecko_id'))
    symbol: Optional[str] = None
    name: Optional[str] = None
    image: Optional[str] = Field(default=None, validation_alias=AliasChoices('image', 'thumb'))
    current_price: Optional[float] = None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    

class AssetOutFromDb(BaseModel):
    id:UUID
    coingecko_id: str
    symbol: str
    name: str
    image: str
    current_price: float
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)   

class AssetOutFromSearch(BaseModel):
    coingecko_id: Optional[str] = Field(default=None, validation_alias=AliasChoices('id', 'coingecko_id'))
    symbol: Optional[str] = None
    name: Optional[str] = None
    image: Optional[str] = Field(default=None, validation_alias=AliasChoices('image', 'thumb'))
    current_price: Optional[float] = None
    
    @classmethod
    def from_search_result(cls,coin_data:Dict[str,Any]) -> 'AssetOutFromSearch':
        return cls(
            coingecko_id=coin_data.get('id'),
            symbol=coin_data.get('symbol', '').upper(),
            name=coin_data.get('name', 'Unknown'),
            image=coin_data.get('thumb') or coin_data.get('image') or "https://via.placeholder.com/50"
        )

class AssetInDb(BaseModel):
  symbol:str
  name:str
  coingecko_id:str
  image:str
  current_price: Optional[float] = 0.0

class AssetIds(BaseModel):
    ids: List[str]

    @field_validator("ids")
    @classmethod
    def invalid_length(cls, asset_ids):
        if len(asset_ids) > 10:
            raise ValueError("You can select maximum 10 crypto!!!")
        return asset_ids  
    
    
class Price(BaseModel):
    usd:float

class AssetWithPrice(BaseModel):
    asset:Dict[str,Price]

class PriceSnapshotOut(BaseModel):
    price_usd:float
    timestamp:datetime
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)