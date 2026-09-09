import uuid
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.user import Bookmark
from app.models.news import News


async def get_bookmark(db: AsyncSession, user_id: uuid.UUID, news_id: int) -> Optional[Bookmark]:
    stmt = select(Bookmark).where(
        and_(Bookmark.user_id == user_id, Bookmark.news_id == news_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def create_bookmark(db: AsyncSession, user_id: uuid.UUID, news_id: int) -> Bookmark:
    bookmark = Bookmark(user_id=user_id, news_id=news_id)
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)
    return bookmark


async def delete_bookmark(db: AsyncSession, bookmark: Bookmark) -> None:
    await db.delete(bookmark)
    await db.commit()


async def get_user_bookmarks(
    db: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> Sequence[News]:
    stmt = (
        select(News)
        .join(Bookmark, Bookmark.news_id == News.id)
        .where(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()