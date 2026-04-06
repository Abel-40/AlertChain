from pydantic import BaseModel,Field
from typing import TypeVar,Generic,Any,Dict,List,Optional

T = TypeVar("T")
class APIResponse(BaseModel,Generic[T]):
  success:bool
  message:str
  errors: Optional[Any] = None 
  data: Optional[T] = None
  meta: Optional[dict] = None
  
class PaginationMeta(BaseModel):
  page:int
  item_size:int
  total_items:int
  total_pages:int

I = TypeVar("I")
class PaginatedResponse(BaseModel, Generic[I]):
  items:List[I]
  meta:PaginationMeta
  
class TokenResponse(BaseModel):
  access_token:str
  token_type:str

class QueryParams(BaseModel):
  page:int = Field(default=1,ge=1)
  page_size:int = Field(default=10,le=100)
  tags:Optional[List[str]] = None