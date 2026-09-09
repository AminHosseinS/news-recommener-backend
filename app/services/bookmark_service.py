from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.crud import crud_bookmark
from app.models.user import User
from app.models.news import News


async def add_bookmark(db: AsyncSession, user: User, news_id: int) -> dict:
    news_result = await db.execute(select(News).where(News.id == news_id))
    news = news_result.scalars().first()
    if not news:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خبر مورد نظر یافت نشد."
        )

    existing_bookmark = await crud_bookmark.get_bookmark(db, user.id, news_id)
    if existing_bookmark:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این خبر قبلاً در لیست ذخیره‌شده‌های شما قرار گرفته است."
        )

    await crud_bookmark.create_bookmark(db, user.id, news_id)
    return {"detail": "خبر با موفقیت ذخیره شد."}


async def remove_bookmark(db: AsyncSession, user: User, news_id: int) -> dict:
    existing_bookmark = await crud_bookmark.get_bookmark(db, user.id, news_id)
    if not existing_bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="این خبر در لیست ذخیره‌شده‌های شما یافت نشد."
        )

    await crud_bookmark.delete_bookmark(db, existing_bookmark)
    return {"detail": "خبر از لیست ذخیره‌شده‌ها حذف شد."}


async def get_bookmarked_news(db: AsyncSession, user: User, skip: int, limit: int):
    return await crud_bookmark.get_user_bookmarks(db, user.id, skip, limit)