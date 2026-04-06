from app.schemas.users import UserCreate,UserInDB,ThirdPartyLogin
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.model import User,AuthAccount
from pydantic import EmailStr
from app.exceptions.users import UserAlreadyExistError, InvalidCredentialsError
from app.core.auth import hash_password,verify_password
from uuid import UUID
from app.tasks.alerts import send_email

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
  auth_account = AuthAccount(provider="local",provider_account_id=user.email,user_id=user.id)
  db.add(auth_account)
  await db.commit()
  return user

async def social_signup(user_data: ThirdPartyLogin, db: AsyncSession):
  existing_auth_account = (await db.execute(
    select(AuthAccount).where(
      AuthAccount.provider==user_data.provider,
      AuthAccount.provider_account_id==user_data.provider_account_id
      )
  )).scalar_one_or_none()
  if existing_auth_account:
    return existing_auth_account.user
  user = await get_user_by_email(email=user_data.email,db=db)
  if not user:
    user = User(email=user_data.email)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    send_email.apply_async(args=[user_data.email,""],queue="simple_task_queue",priority=7)
    
  auth_account = AuthAccount(provider=user_data.provider,provider_account_id=user_data.provider_account_id,user_id=user.id)
  db.add(auth_account)
  await db.commit()
  return user
  
  
async def reset_password_service(user_id: UUID, new_password: str, db: AsyncSession):
    user = await get_user_by_id(db=db, id=user_id)
    if not user:
        raise InvalidCredentialsError
    user.hashed_password = hash_password(password=new_password)
    await db.commit()
    return user