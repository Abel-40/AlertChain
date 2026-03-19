from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.models.model import User
from sqlalchemy import select
from pwdlib import  PasswordHash
from typing import Dict
from datetime import timedelta,datetime
from pydantic import EmailStr
from app.core.config import settings
from app.services.auth import get_user_by_email
import jwt
password_hasher = PasswordHash.recommended()

def hash_password(password:str):
  return password_hasher.hash(password=password)

def verify_password(password:str,password_in_db:str):
  return password_hasher.verify(password=password,hash=password_in_db)

async def authenticate_user(db:AsyncSession,email:EmailStr,password:str):
  user = await get_user_by_email(db=db,email=email)
  if not user:
    return False
  if not verify_password(password,user.hashed_password):
    return False
  return user

async def token_generator(data:Dict,expire:timedelta,key:str):
  to_encode = data.copy()
  expire = datetime.now() + expire
  to_encode.update({"exp":expire})
  token = jwt.encode(to_encode,key=key,algorithm=settings.ALGO)
  return token

