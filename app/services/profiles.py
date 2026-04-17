from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.model import UserProfile, User
from app.schemas.profiles import UserProfileCreate, UserProfileUpdate
from fastapi import HTTPException, status
from uuid import UUID

async def get_or_create_user_profile(user_id: UUID, db: AsyncSession) -> UserProfile:
    """Get user profile or create one with defaults"""
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    
    if not profile:
        # Create profile with defaults
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    
    return profile

async def get_user_profile(user_id: UUID, db: AsyncSession) -> UserProfile:
    """Get user profile"""
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    return profile

async def update_user_profile(
    user_id: UUID, 
    profile_data: UserProfileUpdate, 
    db: AsyncSession
) -> UserProfile:
    """Update user profile"""
    profile = await get_user_profile(user_id, db)
    
    # Update only provided fields
    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    
    await db.commit()
    await db.refresh(profile)
    return profile
