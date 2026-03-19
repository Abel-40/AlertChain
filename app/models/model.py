from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import String, ForeignKey, DateTime, func, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from pydantic import EmailStr
from typing import Literal
from uuid import uuid4, UUID as UUID_TYPE
from app.db.base import Base
from datetime import datetime

class User(Base):
  __tablename__ = "users"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  email: Mapped[EmailStr] = mapped_column(String, unique=True, index=True)
  full_name: Mapped[str] = mapped_column(String)
  hashed_password: Mapped[str] = mapped_column(String)
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class Asset(Base):
  __tablename__ = "assets"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  symbol: Mapped[str] = mapped_column(String, unique=True)
  name: Mapped[str] = mapped_column(String, unique=True, index=True)
  coingecko_id: Mapped[str] = mapped_column(String, unique=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class PriceSnapshot(Base): 
  __tablename__ = "price_snapshots"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  asset_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"))
  price_usd: Mapped[float] = mapped_column(Float)
  timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class AlertRule(Base):
  __tablename__ = "alert_rules"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
  asset_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"))
  target_price: Mapped[float] = mapped_column(Float)
  condition_type: Mapped[Literal["ABOVE", "BELOW"]] = mapped_column(String)

class Notification(Base):
  __tablename__ = "notifications"
  id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
  user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
  alert_rule_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), ForeignKey("alert_rules.id"))
  message: Mapped[str] = mapped_column(Text)
  status: Mapped[Literal["PENDING", "SENT", "FAILED"]] = mapped_column(String, default="PENDING")
  created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())