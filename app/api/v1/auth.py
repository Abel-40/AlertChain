from fastapi import APIRouter,Depends, HTTPException, status,Request
from fastapi.responses import JSONResponse
from app.services.auth import create_user,authenticate_user,get_user_by_id
from app.schemas.users import UserOut,UserCreate,UserLogin
from app.schemas.responses import APIResponse,TokenResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.db import get_db
from app.utils.response import success_response
from app.exceptions.users import UserAlreadyExistError, InvalidCredentialsError
from app.api.dependencies import rate_limit
from app.core.auth import token_generator
from datetime import timedelta
from app.core.config import settings
from fastapi.security import OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from app.workers.celery_app import check_smtp_task,send_email
import jwt

router = APIRouter(prefix="/auth",tags=["auth"])
@router.post("/register_user/",response_model=APIResponse[UserOut],dependencies=[Depends(rate_limit(limit=5,window=60))])
async def register_user(user_data:UserCreate, db:AsyncSession = Depends(get_db)):
  try:
    user = await create_user(db=db,user_data=user_data)
    send_email.apply_async(args=[user_data.email,user_data.full_name],queue="simple_task_queue",priority=7)
    return success_response(
      status_code=201,
      message="user successfully sign up!!",
      data=UserOut.model_validate(user).model_dump(mode="json"),
      )
  except UserAlreadyExistError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Email already exist!!!")
      
@router.post("/login/",response_model=APIResponse[UserOut],dependencies=[Depends(rate_limit(limit=5,window=60))])
async def login_endpoint(user_data:OAuth2PasswordRequestForm = Depends(),db:AsyncSession = Depends(get_db)):
  try:
      user = await authenticate_user(db=db,email=user_data.username,password=user_data.password)
      access_token = token_generator(data={"sub":str(user.id),"type":"access"},expire=timedelta(minutes=30),key=settings.ACCESS_TOKEN_KEY)
      refresh_token = token_generator(data={"sub":str(user.id),"type":"refresh"},expire=timedelta(days=30),key=settings.REFRESH_TOKEN_KEY)
      response =  JSONResponse(
      status_code=200,
      content=TokenResponse(access_token=access_token,token_type="Bearer").model_dump()
    )
      response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        max_age=3600 * 24 * 7
      )
      return response
  except InvalidCredentialsError:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Invalid Email or Password")

@router.post("/refresh")
async def refresh_login(request: Request, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Refresh token missing"
        )

    try:
        payload = jwt.decode(
            refresh_token, 
            settings.REFRESH_TOKEN_KEY, 
            algorithms=[settings.ALGO]
        )
        
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
            
        user_id = payload.get("sub")
        user = await get_user_by_id(id=user_id, db=db)
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        new_access = token_generator(
            data={"sub": str(user.id), "type": "access"},
            expire=timedelta(minutes=30),
            key=settings.ACCESS_TOKEN_KEY
        )
        new_refresh = token_generator(
            data={"sub": str(user.id), "type": "refresh"},
            expire=timedelta(days=30),
            key=settings.REFRESH_TOKEN_KEY
        )

        response = success_response(
            status_code=200,
            message="Token refreshed",
            data=TokenResponse(access_token=new_access, token_type="Bearer").model_dump()
        )

        response.set_cookie(
            key="refresh_token",
            value=new_refresh,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600 * 24 * 7
        )
        return response

    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
   
@router.get("/check_email/") 
async def check_smtp():
    print(check_smtp_task.run())
    