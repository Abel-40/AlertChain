from pydantic import BaseModel,ConfigDict,Field, AliasChoices,field_validator
from uuid import UUID
from fastapi import HTTPException,status
from typing import List,Annotated
class AssetOut(BaseModel):
    coingecko_id: str = Field(validation_alias=AliasChoices('id', 'coingecko_id'))
    symbol: str
    name: str
    image: str = Field(validation_alias=AliasChoices('image', 'thumb'))
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AssetInDb(BaseModel):
  symbol:str
  name:str
  coingecko_id:str
  image:str

class AssetIds(BaseModel):
    ids: List[str]

    @field_validator("ids")
    @classmethod
    def invalid_length(cls, asset_ids):
        if len(asset_ids) > 10:
            raise ValueError("You can select maximum 10 crypto!!!")
        return asset_ids  