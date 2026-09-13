from typing import List

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.router.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserFavoriteTagsRequest, UserFavoriteTagsResponse
from app.services import user_service
from app.services import bookmark_service
from app.crud import crud_bookmark
from app.schemas.feed import PaginatedNewsListResponse
from app.schemas.user import UserProfileResponse

router = APIRouter()


@router.get("/favorite-tags", response_model=UserFavoriteTagsResponse)
async def get_favorite_tags(
        current_user: User = Depends(get_current_user)
):
    return UserFavoriteTagsResponse(tags=current_user.favorite_tags or [])


@router.put("/favorite-tags", response_model=UserFavoriteTagsResponse)
async def update_favorite_tags(
        request: UserFavoriteTagsRequest,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    updated_user = await user_service.update_favorite_tags(
        db=db,
        user=current_user,
        tag_slugs=request.tags
    )
    return UserFavoriteTagsResponse(tags=updated_user.favorite_tags)

@router.post("/bookmarks/{news_id}", status_code=status.HTTP_201_CREATED)
async def bookmark_news(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await bookmark_service.add_bookmark(db, current_user, news_id)


@router.delete("/bookmarks/{news_id}", status_code=status.HTTP_200_OK)
async def remove_news_bookmark(
    news_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await bookmark_service.remove_bookmark(db, current_user, news_id)

@router.get("/bookmarks", response_model=PaginatedNewsListResponse)
async def get_bookmarked_news_list(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=50),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    news_list = await crud_bookmark.get_user_bookmarks(db, current_user.id, skip, limit + 1)

    has_more = len(news_list) > limit

    if has_more:
        news_list = news_list[:-1]
        next_offset = skip + limit
    else:
        next_offset = None

    return PaginatedNewsListResponse(
        data=news_list,
        next_offset=next_offset
    )

@router.get("/me", response_model=UserProfileResponse)
async def get_user_profile(
        current_user: User = Depends(get_current_user)
):
    return UserProfileResponse(
        phone_number=current_user.phone_number,
        is_connected_to_bale=bool(current_user.bale_chat_id)
    )