from sqlalchemy import select
from pwdlib import  PasswordHash
from typing import Dict
from datetime import timedelta,datetime
from app.core.config import settings
import jwt
password_hasher = PasswordHash.recommended()

def hash_password(password:str):
  return password_hasher.hash(password=password)

def verify_password(password:str,password_in_db:str):
  return password_hasher.verify(password=password,hash=password_in_db)

def token_generator(data:Dict,expire:timedelta,key:str):
  to_encode = data.copy()
  expire = datetime.now() + expire
  to_encode.update({"exp":expire})
  token = jwt.encode(to_encode,key=key,algorithm=settings.ALGO)
  return token

