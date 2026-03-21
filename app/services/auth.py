from app.schemas.users import UserCreate,UserInDB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.model import User
from pydantic import EmailStr
from app.exceptions.users import UserAlreadyExistError, InvalidCredentialsError
from app.core.auth import hash_password,verify_password
from uuid import UUID


async def get_user_by_id(db:AsyncSession, id:UUID):
  stmt = select(User).where(User.id == id)
  result = await db.scalars(stmt)
  return result.one_or_none()

async def get_user_by_email(db:AsyncSession,email:EmailStr):
  stmt = select(User).where(User.email == email)
  result = await db.scalars(stmt)
  return result.one_or_none()

async def authenticate_user(db:AsyncSession,email:EmailStr,password:str):
  user = await get_user_by_email(db=db,email=email)
  if not user:
    raise InvalidCredentialsError
  if not verify_password(password,user.hashed_password):
    raise InvalidCredentialsError
  return user


async def create_user(db:AsyncSession,user_data:UserCreate):
  user = await get_user_by_email(db=db, email=user_data.email)
  if user:
    raise UserAlreadyExistError
  user_data = UserInDB(**user_data.model_dump(exclude="password"),hashed_password=hash_password(password=user_data.password))
  user = User(**user_data.model_dump())
  db.add(user)
  await db.commit()
  await db.flush()
  await db.refresh(user)
  return user