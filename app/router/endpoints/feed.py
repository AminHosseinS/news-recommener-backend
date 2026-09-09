from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient

from app.database.session import get_db
from app.database.qdrant import get_qdrant
from app.database.redis import get_redis
from app.router.deps import get_current_user
from app.models.user import User
from app.schemas.feed import WebFeedResponse, TrackImpressionRequest, NewsFeedItem, NewsSearchResponse
from app.services.feed_service import get_personalized_feed, bg_process_interactions
from app.services.search_service import execute_search
from app.schemas.feed import NewsListItem
from app.models.news import News
from app.schemas.feed import NewsDetailResponse

router = APIRouter()

@router.get("/web", response_model=WebFeedResponse)
async def get_web_feed(
        background_tasks: BackgroundTasks,
        offset: int = 0,
        limit: int = 10,
        refresh: bool = False,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        redis_client: redis.Redis = Depends(get_redis),
        qdrant_client: AsyncQdrantClient = Depends(get_qdrant)
):
    news_list = await get_personalized_feed(
        user=current_user,
        platform="web",
        limit=limit,
        offset=offset,
        db=db,
        redis_client=redis_client,
        qdrant_client=qdrant_client,
        bg_tasks=background_tasks,
        refresh=refresh
    )

    next_offset = (offset + len(news_list)) if news_list else None
    parsed_news = [NewsFeedItem.model_validate(n) for n in news_list]

    return WebFeedResponse(
        data=parsed_news,
        next_offset=next_offset,
    )

@router.post("/web/track-view")
async def track_web_impression(
        request: TrackImpressionRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        redis_client: redis.Redis = Depends(get_redis),
        qdrant_client: AsyncQdrantClient = Depends(get_qdrant)
):
    if not request.interactions:
        return {"status": "ignored"}

    background_tasks.add_task(
        bg_process_interactions,
        user_id=current_user.id,
        request=request,
        redis_client=redis_client,
        qdrant_client=qdrant_client
    )

    return {"status": "success", "tracked_count": len(request.interactions)}

@router.get("/search", response_model=List[NewsListItem])
async def search_news(
    q: str = Query(..., min_length=2, description="Search Query"),
    limit: int = Query(10, ge=1, le=50, description="Result Count"),
    db: AsyncSession = Depends(get_db),
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    current_user: User = Depends(get_current_user)
):
    results = await execute_search(db=db, qdrant=qdrant, query=q, limit=limit)
    return results


@router.get("/{news_id}", response_model=NewsDetailResponse)
async def get_single_news(
        news_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):

    result = await db.execute(select(News).where(News.id == news_id))
    news = result.scalars().first()

    if not news:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خبر مورد نظر یافت نشد"
        )

    return news

# needs rework !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
@router.post("/bot/next-news")
async def get_bot_next_news(
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        redis_client: redis.Redis = Depends(get_redis),
        qdrant_client: AsyncQdrantClient = Depends(get_qdrant)
):
    # برای ربات بله همیشه offset=0 و limit=1 است
    news_list = await get_personalized_feed(
        user=current_user,
        platform="bot",
        limit=1,
        offset=0,
        db=db,
        redis_client=redis_client,
        qdrant_client=qdrant_client,
        bg_tasks=background_tasks
    )

    if not news_list:
        return {"text": "خبر جدیدی برای شما یافت نشد! لطفا بعدا سر بزنید."}

    news = news_list[0]

    bot_message_text = f"**{news.title}**\n\n{news.ai_summary or ''}\n\n[لینک خبر]({news.link})"

    return {
        "chat_id": current_user.bale_chat_id,
        "text": bot_message_text,
        "image": news.image_url,
        "keyboard": {
            "inline_keyboard": [
                [{"text": "👍 می‌پسندم", "callback_data": f"like_{news.id}"}],
                [{"text": "➡️ خبر بعدی", "callback_data": "next_news"}]
            ]
        }
    }