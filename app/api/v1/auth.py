from fastapi import APIRouter,Depends, HTTPException, status,Request
from fastapi.responses import JSONResponse
from app.services.auth import create_user,authenticate_user,get_user_by_id,social_signup, get_user_by_email, reset_password_service
from app.schemas.users import UserOut,UserCreate,UserLogin,ThirdPartyLogin, ForgotPassword, ResetPassword
from app.schemas.responses import APIResponse,TokenResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.db import get_db
from app.models.model import User
from app.utils.response import success_response
from app.exceptions.users import UserAlreadyExistError, InvalidCredentialsError
from app.api.dependencies import rate_limit, auth_scheme
from app.core.auth import token_generator
import hashlib
from uuid import UUID, uuid4
from datetime import timedelta
from app.core.config import settings
from fastapi.security import OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from app.tasks.alerts import send_email, check_smtp_task,send_email_forget_password
from app.api.dependencies import get_current_user
import jwt
import time




router = APIRouter(prefix="/auth",tags=["auth"])
@router.post("/register_user/",response_model=APIResponse[UserOut],dependencies=[Depends(rate_limit(limit=5,window=60))])
async def register_user(user_data:UserCreate, db:AsyncSession = Depends(get_db)):
  try:
    user = await create_user(db=db,user_data=user_data)
    send_email.apply_async(args=[user_data.email,user_data.full_name],queue="simple_task_queue",priority=7)
    return success_response(
      status_code=201,
      message="user successfully sign up!!",
      data=UserOut.model_validate(user),
      )
  except UserAlreadyExistError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="Email already exist!!!")
      
@router.post("/login/",response_model=APIResponse[UserOut],dependencies=[Depends(rate_limit(limit=10,window=60))])
async def login_endpoint(user_data:OAuth2PasswordRequestForm = Depends(),db:AsyncSession = Depends(get_db), request: Request = None):
  try:
      user = await authenticate_user(db=db,email=user_data.username,password=user_data.password)
      access_token = token_generator(data={"sub":str(user.id),"type":"access"},expire=timedelta(minutes=30),key=settings.ACCESS_TOKEN_KEY)
      refresh_token, refresh_jti = token_generator(data={"sub":str(user.id),"type":"refresh"},expire=timedelta(days=30),key=settings.REFRESH_TOKEN_KEY, return_jti=True)
      # persist refresh jti (hashed) in Redis for rotation/revocation
      ttl = int(timedelta(days=30).total_seconds())
      try:
          redis = request.app.state.redis
          hashed = hashlib.sha256(refresh_jti.encode()).hexdigest()
          await redis.set(f"refresh_jti:{hashed}", str(user.id), ex=ttl)
      except Exception:
          # don't fail login on redis issues, but log in real app
          pass
      response =  JSONResponse(
      status_code=200,
      content=TokenResponse(access_token=access_token,token_type="Bearer").model_dump()
    )
      response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
                samesite="lax",
                max_age=ttl
      )
      return response
  except InvalidCredentialsError:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Invalid Email or Password")

@router.post("/refresh", dependencies=[Depends(rate_limit(limit=10, window=60))])
async def refresh_login(request: Request, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Refresh token missing"
        )
    
    redis = request.app.state.redis
    try:
        payload = jwt.decode(
            refresh_token,
            settings.REFRESH_TOKEN_KEY,
            algorithms=[settings.ALGO],
            audience=settings.JWT_AUD,
            issuer=settings.JWT_ISS,
        )

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        refresh_jti = payload.get("jti")
        if not refresh_jti:
            raise HTTPException(status_code=401, detail="Invalid token")

        hashed = hashlib.sha256(refresh_jti.encode()).hexdigest()
        stored = await redis.get(f"refresh_jti:{hashed}")
        if not stored:
            # token revoked or rotated
            raise HTTPException(status_code=401, detail="Refresh token revoked")

        user_id = payload.get("sub")
        user = await get_user_by_id(id=user_id, db=db)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        # rotation: remove old jti and create a new one
        try:
            await redis.delete(f"refresh_jti:{hashed}")
        except Exception:
            pass

        new_access = token_generator(
            data={"sub": str(user.id), "type": "access"},
            expire=timedelta(minutes=30),
            key=settings.ACCESS_TOKEN_KEY
        )
        new_refresh, new_jti = token_generator(
            data={"sub": str(user.id), "type": "refresh"},
            expire=timedelta(days=30),
            key=settings.REFRESH_TOKEN_KEY,
            return_jti=True,
        )

        # persist new jti
        try:
            new_hashed = hashlib.sha256(new_jti.encode()).hexdigest()
            ttl = int(timedelta(days=30).total_seconds())
            await redis.set(f"refresh_jti:{new_hashed}", str(user.id), ex=ttl)
        except Exception:
            pass

        response = success_response(
            status_code=200,
            message="Token refreshed",
            data=TokenResponse(access_token=new_access, token_type="Bearer")
        )

        response.set_cookie(
            key="refresh_token",
            value=new_refresh,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=ttl,
        )
        return response

    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    
@router.post("/social/signup", dependencies=[Depends(rate_limit(limit=5, window=60))])
async def third_party_signup(user_data:ThirdPartyLogin, db:AsyncSession = Depends(get_db), request: Request = None):
    user = await social_signup(user_data=user_data,db=db)
    access_token = token_generator(data={"sub":str(user.id),"type":"access"},expire=timedelta(minutes=30),key=settings.ACCESS_TOKEN_KEY)
    refresh_token, refresh_jti = token_generator(data={"sub":str(user.id),"type":"refresh"},expire=timedelta(days=30),key=settings.REFRESH_TOKEN_KEY, return_jti=True)
    response =  JSONResponse(
    status_code=200,
    content=TokenResponse(access_token=access_token,token_type="Bearer").model_dump()
)
    try:
        redis = request.app.state.redis
        hashed = hashlib.sha256(refresh_jti.encode()).hexdigest()
        ttl = int(timedelta(days=30).total_seconds())
        await redis.set(f"refresh_jti:{hashed}", str(user.id), ex=ttl)
    except Exception:
        pass

    response.set_cookie(
    key="refresh_token",
    value=refresh_token,
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=ttl
    )
    return response
   
@router.get("/check_email/") 
async def check_smtp():
    print(check_smtp_task.run())

@router.get("/me/", response_model=APIResponse[UserOut])
async def get_me(current_user: User = Depends(get_current_user)):
    return success_response(
        status_code=200,
        message="Current user fetched successfully",
        data=UserOut.model_validate(current_user)
    )

@router.post("/logout/", dependencies=[Depends(rate_limit(limit=10, window=60))])
async def logout(request: Request, token: str = Depends(auth_scheme)):
    response = success_response(
        status_code=200,
        message="Logged out successfully",
        data=None
    )
    redis = request.app.state.redis
    refresh_token = request.cookies.get("refresh_token")

    try:
        payload = jwt.decode(
            token,
            settings.ACCESS_TOKEN_KEY,
            algorithms=[settings.ALGO],
            options={"verify_exp": False},
            audience=settings.JWT_AUD,
            issuer=settings.JWT_ISS,
        )
        exp = payload.get("exp", 0)
        now = time.time()
        ttl = max(0, int(exp - now))
        jti = payload.get("jti")
        if ttl > 0 and jti:
            await redis.set(f"blacklist:access_jti:{jti}", "1", ex=ttl)
    except Exception:
        pass

    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.REFRESH_TOKEN_KEY,
                algorithms=[settings.ALGO],
                options={"verify_exp": False},
                audience=settings.JWT_AUD,
                issuer=settings.JWT_ISS,
            )
            refresh_jti = payload.get("jti")
            if refresh_jti:
                hashed = hashlib.sha256(refresh_jti.encode()).hexdigest()
                await redis.delete(f"refresh_jti:{hashed}")
        except Exception:
            pass

    response.delete_cookie(key="refresh_token")
    return response

@router.post("/forgot-password", dependencies=[Depends(rate_limit(limit=5, window=60))])
async def forgot_password(payload: ForgotPassword, db: AsyncSession = Depends(get_db), request: Request = None):
    # Always return the same message to avoid user enumeration
    user = await get_user_by_email(email=payload.email, db=db)
    # generate a one-time reset code and store hashed value in Redis
    reset_code = uuid4().hex

    try:
        if user:
            hashed = hashlib.sha256(reset_code.encode()).hexdigest()
            redis = request.app.state.redis
            await redis.set(f"pwd_reset:{hashed}", str(user.id), ex=int(timedelta(minutes=15).total_seconds()))
            # include the one-time code in the URL so the frontend can auto-fill the form
            reset_link = f"https://localhost:5173/reset-password?code={reset_code}"
            send_email_forget_password.apply_async(args=[reset_link, payload.email, reset_code], queue="simple_task_queue", priority=7)
    except Exception:
        # log in real app
        pass

    return success_response(
        status_code=200,
        message="If an account exists, a password reset email has been sent.",
        data=None,
    )

@router.post("/reset-password", dependencies=[Depends(rate_limit(limit=5, window=60))])
async def reset_password(payload: ResetPassword, db: AsyncSession = Depends(get_db), request: Request = None):
    # Payload must include `code` (one-time code from email)
    try:
        redis = request.app.state.redis
        hashed = hashlib.sha256(payload.code.encode()).hexdigest()
        user_id = await redis.get(f"pwd_reset:{hashed}")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset code")

        # redis returns bytes; ensure string
        if isinstance(user_id, bytes):
            user_id = user_id.decode()

        await reset_password_service(user_id=UUID(user_id), new_password=payload.new_password, db=db)
        # consume the code
        await redis.delete(f"pwd_reset:{hashed}")
        return success_response(
            status_code=200,
            message="Password reset successfully.",
            data=None
        )
    except InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user not found")