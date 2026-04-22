from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
import re
from uuid import UUID
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str  

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r"[@$!%*?&#]", v):
            raise ValueError('Password must contain at least one special character (@, $, !, %, *, ?, &, #)')
        return v
class UserOut(UserBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UserInDB(UserBase):
    hashed_password: str
    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    email:EmailStr
    password:str
    
    
class ThirdPartyLogin(BaseModel):
  provider:str
  email:EmailStr
  provider_account_id:str

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    new_password: str
    code: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r"[@$!%*?&#]", v):
            raise ValueError('Password must contain at least one special character (@, $, !, %, *, ?, &, #)')
        return v