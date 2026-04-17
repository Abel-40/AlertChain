from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from uuid import UUID
from datetime import datetime

class UserProfileCreate(BaseModel):
    """Schema for creating user profile"""
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    preferred_currency: str = "USD"
    risk_tolerance: Literal["LOW", "MEDIUM", "HIGH", "VERY_HIGH"] = "MEDIUM"
    trading_experience: Literal["BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"] = "BEGINNER"
    email_notifications: bool = True
    price_alert_notifications: bool = True
    market_update_notifications: bool = False
    newsletter_subscription: bool = False
    theme: Literal["LIGHT", "DARK", "SYSTEM"] = "DARK"
    default_chart_timeframe: str = "1D"
    show_portfolio_on_dashboard: bool = True
    default_alert_condition: Literal["ABOVE", "BELOW"] = "ABOVE"
    alert_cooldown_minutes: int = 60
    max_active_alerts: int = 50

class UserProfileUpdate(BaseModel):
    """Schema for updating user profile"""
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    preferred_currency: Optional[str] = None
    risk_tolerance: Optional[Literal["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]] = None
    trading_experience: Optional[Literal["BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"]] = None
    email_notifications: Optional[bool] = None
    price_alert_notifications: Optional[bool] = None
    market_update_notifications: Optional[bool] = None
    newsletter_subscription: Optional[bool] = None
    theme: Optional[Literal["LIGHT", "DARK", "SYSTEM"]] = None
    default_chart_timeframe: Optional[str] = None
    show_portfolio_on_dashboard: Optional[bool] = None
    default_alert_condition: Optional[Literal["ABOVE", "BELOW"]] = None
    alert_cooldown_minutes: Optional[int] = None
    max_active_alerts: Optional[int] = None

class UserProfileOut(BaseModel):
    """Schema for user profile response"""
    id: UUID
    user_id: UUID
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    preferred_currency: str
    risk_tolerance: str
    trading_experience: str
    email_notifications: bool
    price_alert_notifications: bool
    market_update_notifications: bool
    newsletter_subscription: bool
    theme: str
    default_chart_timeframe: str
    show_portfolio_on_dashboard: bool
    default_alert_condition: str
    alert_cooldown_minutes: int
    max_active_alerts: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
