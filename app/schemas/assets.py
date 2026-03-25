from pydantic import BaseModel,ConfigDict,Field, AliasChoices

class AssetOut(BaseModel):
    coingecko_id: str = Field(validation_alias=AliasChoices('id', 'coingecko_id'))
    symbol: str
    name: str
    image: str = Field(validation_alias=AliasChoices('image', 'thumb'))
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
