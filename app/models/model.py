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
  
class Asset(Base):
  __tablename__ = "assets"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  symbol: Mapped[str] = mapped_column(String, index=True)
  name: Mapped[str] = mapped_column(String, index=True)
  coingecko_id: Mapped[str] = mapped_column(String, unique=True)
  image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  
  price_snapshots: Mapped[List["PriceSnapshot"]] = relationship(
    "PriceSnapshot",
    back_populates="asset",
    passive_deletes=True
    )
  
class PriceSnapshot(Base): 
  __tablename__ = "price_snapshots"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  asset_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id",ondelete="CASCADE"))
  price_usd: Mapped[float] = mapped_column(Float)
  timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  asset: Mapped["Asset"] = relationship("Asset", back_populates="price_snapshots")

class AlertRule(Base):
  __tablename__ = "alert_rules"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="CASCADE"))
  asset_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"))
  target_price: Mapped[float] = mapped_column(Float)
  condition_type: Mapped[Literal["ABOVE", "BELOW"]] = mapped_column(String)
  is_active:Mapped[bool] = mapped_column(Boolean,index=True)
  user:Mapped[User] = relationship('User',back_populates="alerts")
  asset: Mapped["Asset"] = relationship("Asset")
  updated_at:Mapped[datetime] = mapped_column(DateTime, onupdate=func.now())
  
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
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
  user: Mapped[User] = relationship("User", back_populates="notifications")
  alert_rule: Mapped["AlertRule"] = relationship("AlertRule")