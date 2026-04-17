from sqlalchemy.orm import mapped_column, Mapped,relationship
from sqlalchemy import String, ForeignKey, DateTime, func, Float, Text,Boolean,UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from pydantic import EmailStr
from typing import Literal,List,Optional
from uuid import uuid4, UUID as UUID_TYPE
from app.db.base import Base
from datetime import datetime

class AuthAccount(Base):
  __tablename__="auth_accounts"
  id:Mapped[UUID] = mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid4)
  provider:Mapped[str] = mapped_column(String(65),nullable=False)
  provider_account_id:Mapped[str] = mapped_column(String(255),nullable=False,unique=True)
  user_id:Mapped[UUID] = mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="CASCADE"),nullable=False)
  created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
  
  user:Mapped["User"] = relationship("User",back_populates="auth_accounts",lazy="selectin")
  
class User(Base):
  __tablename__ = "users"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  email: Mapped[EmailStr] = mapped_column(String, unique=True, index=True,nullable=False)
  full_name: Mapped[str] = mapped_column(String,nullable=True)
  hashed_password: Mapped[str] = mapped_column(String,nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  updated_at: Mapped[datetime] = mapped_column(
      DateTime,
      default=datetime.utcnow,
      onupdate=datetime.utcnow
  )

  alerts:Mapped[List["AlertRule"]] = relationship("AlertRule",back_populates="user",lazy="selectin",passive_deletes=True)
  auth_accounts:Mapped[List[AuthAccount]] = relationship("AuthAccount",back_populates="user",passive_deletes=True)
  notifications: Mapped[List["Notification"]] = relationship(
      "Notification",
      back_populates="user",
      passive_deletes=True
  )
  user_assets:Mapped[List["UserAsset"]] = relationship("UserAsset",back_populates="user",cascade="all, delete-orphan",passive_deletes=True)
  profile: Mapped[Optional["UserProfile"]] = relationship("UserProfile", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
  
class Asset(Base):
  __tablename__ = "assets"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  symbol: Mapped[str] = mapped_column(String, index=True)
  name: Mapped[str] = mapped_column(String, index=True)
  coingecko_id: Mapped[str] = mapped_column(String, unique=True, index=True)
  image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
  current_price: Mapped[float] = mapped_column(Float, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  
  price_snapshots: Mapped[List["PriceSnapshot"]] = relationship(
    "PriceSnapshot",
    back_populates="asset",
    passive_deletes=True
    )
  user_assets:Mapped[List["UserAsset"]] = relationship("UserAsset",back_populates="asset")
  
class PriceSnapshot(Base): 
  __tablename__ = "price_snapshots"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  asset_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id",ondelete="CASCADE"))
  price_usd: Mapped[float] = mapped_column(Float)
  timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  
  asset: Mapped["Asset"] = relationship("Asset", back_populates="price_snapshots")


class UserAsset(Base):
  """Junction table for many-to-many relationship between User and Asset"""
  __tablename__ = "user_assets"
  __table_args__ = (
    UniqueConstraint("user_id", "asset_id", name="uq_user_asset"),
  )
  
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
  asset_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
  added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  
  # Relationships
  user: Mapped["User"] = relationship("User", back_populates="user_assets")
  asset: Mapped["Asset"] = relationship("Asset", back_populates="user_assets")

class AlertRule(Base):
  __tablename__ = "alert_rules"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
  asset_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"))
  target_price: Mapped[float] = mapped_column(Float)
  condition_type: Mapped[Literal["ABOVE", "BELOW"]] = mapped_column(String)
  is_active:Mapped[bool] = mapped_column(Boolean,default=True,index=True)
  last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  updated_at: Mapped[datetime] = mapped_column(
      DateTime,
      default=datetime.utcnow,
      onupdate=datetime.utcnow
  )
  
  user:Mapped[User] = relationship('User',back_populates="alerts")
  asset: Mapped["Asset"] = relationship("Asset",lazy="selectin")
  
  
  __table_args__ = (
    UniqueConstraint("user_id","asset_id","target_price","condition_type"),
  )

  
  
class Notification(Base):
  __tablename__ = "notifications"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
  alert_rule_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("alert_rules.id"))
  message: Mapped[str] = mapped_column(Text)
  status: Mapped[Literal["PENDING", "SENT", "FAILED"]] = mapped_column(String, default="PENDING")
  is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  
  user: Mapped[User] = relationship("User", back_populates="notifications")
  alert_rule: Mapped["AlertRule"] = relationship("AlertRule", lazy="selectin")


class UserProfile(Base):
  """User profile settings and preferences"""
  __tablename__ = "user_profiles"
  
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
  
  # Profile Information
  bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
  location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
  website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
  
  # Trading Preferences
  preferred_currency: Mapped[str] = mapped_column(String(10), default="USD")
  risk_tolerance: Mapped[Literal["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]] = mapped_column(String, default="MEDIUM")
  trading_experience: Mapped[Literal["BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"]] = mapped_column(String, default="BEGINNER")
  
  # Notification Settings
  email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
  price_alert_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
  market_update_notifications: Mapped[bool] = mapped_column(Boolean, default=False)
  newsletter_subscription: Mapped[bool] = mapped_column(Boolean, default=False)
  
  # Display Settings
  theme: Mapped[Literal["LIGHT", "DARK", "SYSTEM"]] = mapped_column(String, default="DARK")
  default_chart_timeframe: Mapped[str] = mapped_column(String(20), default="1D")
  show_portfolio_on_dashboard: Mapped[bool] = mapped_column(Boolean, default=True)
  
  # Alert Defaults
  default_alert_condition: Mapped[Literal["ABOVE", "BELOW"]] = mapped_column(String, default="ABOVE")
  alert_cooldown_minutes: Mapped[int] = mapped_column(default=60)
  max_active_alerts: Mapped[int] = mapped_column(default=50)
  
  # Metadata
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  updated_at: Mapped[datetime] = mapped_column(
      DateTime,
      default=datetime.utcnow,
      onupdate=datetime.utcnow
  )
  
  # Relationships
  user: Mapped["User"] = relationship("User", back_populates="profile", lazy="selectin")