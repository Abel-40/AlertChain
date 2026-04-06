from fastapi import Request, HTTPException,status,Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.db import get_db
from app.services.auth import get_user_by_id
from app.core.config import settings
from jwt.exceptions import PyJWTError
import uuid
import time
import jwt

auth_scheme = OAuth2PasswordBearer(tokenUrl="/alertchain/auth/login/")


def rate_limit(limit: int, window: int):
  async def actual_dependency(request: Request):
    
    client_ip = request.client.host
    key = f"throttle:{client_ip}"
    
    now = time.time()
    window_start = now - window
    request_id = str(uuid.uuid4())
    script_obj = request.app.state.rate_limit_script
    result = await script_obj(
        keys=[key], 
        args=[window_start, window, now, limit, request_id]
    )

    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
            detail="Rate limit exceeded. Try again later."
        )
  return actual_dependency
  
  
async def get_current_user(request: Request, token:str = Depends(auth_scheme),db:AsyncSession= Depends(get_db)):
    credentials_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Invalid credentials")
    
    redis = request.app.state.redis
    is_blacklisted = await redis.get(f"blacklist:{token}")
    if is_blacklisted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")

    try:
        payload = jwt.decode(token, settings.ACCESS_TOKEN_KEY, algorithms=[settings.ALGO])
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "access":
            raise credentials_exception
        user = await get_user_by_id(db=db,id=user_id)
        if not user:
            raise credentials_exception
        return user
    except PyJWTError as e:
        print("JWT ERROR TYPE:", type(e).__name__)
        print("JWT ERROR MSG:", str(e))
        raise credentials_exception
