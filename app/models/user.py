import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, ForeignKey, DateTime, Index, UniqueConstraint, BigInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID, REAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number: Mapped[Optional[str]] = mapped_column(String(15), unique=True)
    bale_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, index=True)
    favorite_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default='{}')
    interest_vector: Mapped[Optional[list[float]]] = mapped_column(ARRAY(REAL))
    is_active: Mapped[bool] = mapped_column(default=True)

    otp_code: Mapped[Optional[str]] = mapped_column(String(6))
    otp_expire: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                  onupdate=func.now())

    # ارتباطات
    interactions: Mapped[List["UserInteraction"]] = relationship(back_populates="user")
    bookmarks: Mapped[List["Bookmark"]] = relationship(back_populates="user")


class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    news_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("news.id", ondelete="CASCADE"))
    interaction_type: Mapped[str] = mapped_column(String(30))
    duration_seconds: Mapped[int] = mapped_column(default=0)
    source_platform: Mapped[str] = mapped_column(String(10), default='web')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ارتباطات
    user: Mapped["User"] = relationship(back_populates="interactions")
    news: Mapped["News"] = relationship(back_populates="interactions")

    __table_args__ = (
        Index('idx_interactions_user_time', user_id, created_at.desc()),
        Index('idx_interactions_filter_seen', user_id, news_id, created_at.desc()),
    )


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    news_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("news.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ارتباطات
    user: Mapped["User"] = relationship(back_populates="bookmarks")
    news: Mapped["News"] = relationship(back_populates="bookmarks")

    __table_args__ = (
        UniqueConstraint('user_id', 'news_id', name='uq_user_bookmark'),
        Index('idx_bookmarks_user', user_id, created_at.desc()),
    )