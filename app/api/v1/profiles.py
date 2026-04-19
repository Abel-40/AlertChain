from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user, rate_limit
from app.schemas.responses import APIResponse
from app.schemas.profiles import UserProfileOut, UserProfileUpdate
from app.models.model import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.db import get_db
from app.services.profiles import get_or_create_user_profile, get_user_profile, update_user_profile

router = APIRouter(prefix="/profile", tags=["profiles"])

@router.get("/", response_model=APIResponse[UserProfileOut], dependencies=[Depends(rate_limit(limit=60, window=60))])
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get or create user profile"""
    profile = await get_or_create_user_profile(user_id=current_user.id, db=db)
    return {
        "status_code": 200,
        "message": "Profile retrieved successfully",
        "data": profile
    }

@router.patch("/", response_model=APIResponse[UserProfileOut], dependencies=[Depends(rate_limit(limit=40, window=60))])
async def update_profile(
    profile_data: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user profile"""
    profile = await update_user_profile(
        user_id=current_user.id,
        profile_data=profile_data,
        db=db
    )
    return {
        "status_code": 200,
        "message": "Profile updated successfully",
        "data": profile
    }
