from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.router.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserFavoriteTagsRequest, UserFavoriteTagsResponse
from app.services import user_service

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