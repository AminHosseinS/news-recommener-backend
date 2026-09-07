from datetime import datetime, timedelta, timezone
from typing import List

import math
from fastapi import BackgroundTasks
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
import redis.asyncio as redis
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import News
from app.models import User

FEED_CACHE_TTL = 30 * 60
SEEN_NEWS_TTL = 7 * 24 * 3600

async def bg_track_impressions(
        redis_client: redis.Redis,
        seen_key: str,
        news_ids: List[int],
        platform: str,
        feed_key: str,
):
    if not news_ids:
        return
    await redis_client.sadd(seen_key, *news_ids)
    await redis_client.expire(seen_key,SEEN_NEWS_TTL)
    if platform == "bot":
        await redis_client.zrem(feed_key, *news_ids)

async def get_personalized_feed(
        user: User,
        platform: str,
        limit: int,
        offset: int,
        db: AsyncSession,
        redis_client: redis.Redis,
        qdrant_client: AsyncQdrantClient,
        bg_tasks: BackgroundTasks,
        refresh: bool = False,
) -> List[News]:

    #  -- part 1 --
    if platform == "web":
        feed_key = f"feed:web:{user.id}"
    elif platform == "bot":
        feed_key = f"feed:bot:{user.bale_chat_id}"
    else:
        raise ValueError("Invalid platform")

    seen_key = f"seen_news:{user.id}"

    if refresh:
        await redis_client.delete(feed_key)

    #  -- part 2 --
    end_index = offset + limit -1
    cached_ids_str = await redis_client.zrange(feed_key, offset, end_index)
    news_ids = [int(nid) for nid in cached_ids_str]

    #  -- part 3 --
    if not news_ids:
        seen_ids_str = await redis_client.smembers(seen_key)
        seen_ids = [int(nid) for nid in seen_ids_str]
        fetched_ids = []

        now_utc = datetime.now(timezone.utc)

        if user.interest_vector:
            must_not_conditions = []
            if seen_ids:
                must_not_conditions.append(
                    qmodels.HasIdCondition(has_id=seen_ids)
                )

            try:
                search_result = await qdrant_client.search(
                    collection_name = "news_articles",
                    query_vector=user.interest_vector,
                    query_filter=qmodels.Filter(must_not=must_not_conditions),
                    limit=200
                )

                qdrant_score = {int(hit.id): hit.score for hit in search_result}

                if qdrant_score:
                    stmt = select(News.id,News.pub_date,News.time_validity).where(
                        News.id.in_(qdrant_score.keys()),
                        News.status != "REJECTED"
                    )
                    res = await db.execute(stmt)
                    meta_rows = res.all()

                    rescored_news = []

                    for row in meta_rows:
                        news_id,pub_date,validity = row.id,row.pub_date,row.time_validity
                        age_hours = (now_utc - pub_date).total_seconds() / 3600
                        q_score = qdrant_score[news_id]

                        decay_multiplier = 1.0

                        if validity == "breaking-news":
                            if age_hours > 24: continue
                            decay_multiplier = math.exp(- (math.log(2) / 6.0) * age_hours)
                        elif validity == "daily-news":
                            if age_hours > 90: continue
                            decay_multiplier = math.exp(- (math.log(2) / 24.0) * age_hours)
                        elif validity == "evergreen":
                            decay_multiplier = 1.0

                        final_score = q_score * decay_multiplier

                        if final_score > 0.1:
                            rescored_news.append((final_score, news_id))

                    rescored_news.sort(key=lambda x: x[0], reverse=True)

                    fetched_ids = [item[1] for item in rescored_news[:50]]
            except Exception as e:
                print(f"Qdrant/Rescoring Error: {e}")
                fetched_ids = []

        if not fetched_ids:
            three_days_ago = now_utc - timedelta(days=3)

            stmt = select(News.id).where(
                or_(
                    News.time_validity == "evergreen",
                    News.pub_date >= three_days_ago,
                ),
                News.status != "REJECTED"
            ).order_by(News.pub_date.desc()).limit(50)

            if seen_ids:
                stmt = stmt.where(News.id.notin_(seen_ids))

            res = await db.execute(stmt)
            fetched_ids = res.scalars().all()
        if not fetched_ids:
            return []

        #  -- part 4 --
        zadd_data = {str(nid): score for score, nid in enumerate(fetched_ids)}
        await redis_client.zadd(feed_key, zadd_data)

        await redis_client.expire(feed_key, FEED_CACHE_TTL)

        news_ids = fetched_ids[offset : offset + limit]

    else:
        await redis_client.expire(feed_key, FEED_CACHE_TTL)

    #  -- part 5 --
    if not news_ids:
        return []

    stmt = select(News).where(
        News.id.in_(news_ids),
        News.status != "REJECTED"
    )
    res = await db.execute(stmt)
    news_rows = res.scalars().all()

    news_dict = {n.id: n for n in news_rows}
    sorted_news = [news_dict[nid] for nid in news_ids if nid in news_dict]

    #  -- part 6 --
    if platform == "bot":
        actual_fetched_ids = [n.id for n in sorted_news]
        bg_tasks.add_task(
            bg_track_impressions,
            redis_client=redis_client,
            seen_key=seen_key,
            news_ids=actual_fetched_ids,
            platform=platform,
            feed_key=feed_key
        )

    return sorted_news
