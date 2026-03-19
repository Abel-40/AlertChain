from app.schemas.users import UserCreate,UserInDB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.model import User
from app.exceptions.users import UserAlreadyExistError
from app.core.auth import hash_password
from uuid import UUID


async def get_user_by_id(db:AsyncSession, id:UUID):
  stmt = select(User).where(User.id == id)
  user = await db.scalar_one_or_none(stmt)
  return user

async def get_user_by_email(db:AsyncSession,email:UUID):
  stmt = select(User).where(User.email == email)
  user = await db.scalar_one_or_none(stmt)
  return user

async def create_user(db:AsyncSession,user_data:UserCreate):
  user = await get_user_by_email(db=db, email=user_data.email)
  if user:
    raise UserAlreadyExistError
  user_data = UserInDB(**user_data.model_dump(exclude="password"),hashed_password=hash_password(password=user_data.password))
  user = User(**user_data.model_dump())
  db.add(**user.model_dump())
  await db.commit()
  await db.flush()
  await db.refresh(user)
  return user