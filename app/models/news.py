from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, ForeignKey, DateTime, Index, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .base import Base

class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    feed_url: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    news: Mapped[List["News"]] = relationship(back_populates="source")


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("news_sources.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500))
    link: Mapped[str] = mapped_column(Text, unique=True)
    ai_summary: Mapped[str] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default='{}')
    pub_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), server_default='processed')
    view_count: Mapped[int] = mapped_column(default=0)
    like_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ارتباطات
    source: Mapped[Optional["NewsSource"]] = relationship(back_populates="news")
    interactions: Mapped[List["UserInteraction"]] = relationship(back_populates="news")
    bookmarks: Mapped[List["Bookmark"]] = relationship(back_populates="news")

    __table_args__ = (
        Index('idx_news_pub_date', pub_date.desc()),
        Index('idx_news_tags', tags, postgresql_using='gin'),
    )