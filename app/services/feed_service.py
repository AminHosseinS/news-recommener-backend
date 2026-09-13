# app/services/feed_service.py
import json
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import BackgroundTasks
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import session as SessionLocal
from app.models.news import News
from app.models.user import User
from app.schemas.feed import TrackImpressionRequest

# Import from extracted layers
from app.utils.feed_utils import calculate_time_decay, calculate_interaction_scores, compute_new_vector
from app.crud.crud_news import (
    get_news_tags_map,
    get_news_meta_for_rescoring,
    get_fallback_news_ids,
    get_news_by_ids_sorted
)

FEED_CACHE_TTL = 30 * 60
SEEN_NEWS_TTL = 7 * 24 * 3600
VECTOR_CACHE_TTL = 7 * 24 * 3600


async def _rescore_and_sort_news(db: AsyncSession, qdrant_scores: dict) -> List[int]:
    if not qdrant_scores:
        return []

    meta_rows = await get_news_meta_for_rescoring(db, list(qdrant_scores.keys()))
    now_utc = datetime.now(timezone.utc)
    rescored_news = []

    for row in meta_rows:
        age_hours = (now_utc - row.pub_date).total_seconds() / 3600
        decay_multiplier = calculate_time_decay(age_hours, row.time_validity)
        final_score = qdrant_scores[row.id] * decay_multiplier
        if final_score > 0.1:
            rescored_news.append((final_score, row.id))

    rescored_news.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in rescored_news]


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
    await redis_client.expire(seen_key, SEEN_NEWS_TTL)

    if platform == "bot":
        await redis_client.zrem(feed_key, *news_ids)


async def bg_process_interactions(
        user_id: uuid.UUID,
        request: TrackImpressionRequest,
        redis_client: redis.Redis,
        qdrant_client: AsyncQdrantClient
):
    if not request.interactions:
        return

    alpha_scores = calculate_interaction_scores(request)
    seen_ids = [item.news_id for item in request.interactions]

    seen_key = f"seen_news:{user_id}"
    await redis_client.sadd(seen_key, *seen_ids)
    await redis_client.expire(seen_key, SEEN_NEWS_TTL)

    if not alpha_scores:
        return

    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if not user:
            return

        vector_key = f"vector:{user_id}"
        cached_vector = await redis_client.get(vector_key)

        current_vector = json.loads(cached_vector) if cached_vector else user.interest_vector
        if not current_vector:
            return

        interacted_news_ids = list(alpha_scores.keys())
        news_tags_map = await get_news_tags_map(db, interacted_news_ids)
        user_tags = set(user.favorite_tags or [])

        points = await qdrant_client.retrieve(
            collection_name="news_articles",
            ids=interacted_news_ids,
            with_vectors=True
        )

        new_vector_list = compute_new_vector(
            current_vector=current_vector,
            alpha_scores=alpha_scores,
            points=points,
            news_tags_map=news_tags_map,
            user_tags=user_tags
        )

        await redis_client.set(vector_key, json.dumps(new_vector_list), ex=VECTOR_CACHE_TTL)

        feed_key = f"feed:web:{user_id}"
        if not await redis_client.exists(feed_key):
            return

        all_seen_str = await redis_client.smembers(seen_key)
        all_seen_ids = [int(x) for x in all_seen_str]

        must_not_conditions = [qmodels.HasIdCondition(has_id=all_seen_ids)] if all_seen_ids else []

        search_result = await qdrant_client.search(
            collection_name="news_articles",
            query_vector=new_vector_list,
            query_filter=qmodels.Filter(must_not=must_not_conditions),
            limit=30
        )

        qdrant_score = {int(hit.id): hit.score for hit in search_result}
        rescored_ids = await _rescore_and_sort_news(db, qdrant_score)
        top_new_ids = rescored_ids[:10]

        if top_new_ids:
            max_score_tuple = await redis_client.zrange(feed_key, -1, -1, withscores=True)
            current_max_score = max_score_tuple[0][1] if max_score_tuple else 0
            zadd_data = {str(nid): current_max_score + i + 1 for i, nid in enumerate(top_new_ids)}
            await redis_client.zadd(feed_key, zadd_data)


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
    if platform == "web":
        feed_key = f"feed:web:{user.id}"
    elif platform == "bot":
        feed_key = f"feed:bot:{user.bale_chat_id}"
    else:
        raise ValueError("Invalid platform")

    seen_key = f"seen_news:{user.id}"
    vector_key = f"vector:{user.id}"

    if refresh or offset == 0:
        await redis_client.delete(feed_key)
        cached_vector_str = await redis_client.get(vector_key)
        if cached_vector_str:
            user.interest_vector = json.loads(cached_vector_str)
            db.add(user)
            await db.commit()
            await redis_client.delete(vector_key)
            print(f"Lazy Sync: User {user.id} vector committed to Postgres.")

        active_vector = user.interest_vector
    else:
        cached_vector_str = await redis_client.get(vector_key)
        active_vector = json.loads(cached_vector_str) if cached_vector_str else user.interest_vector

    end_index = offset + limit - 1
    cached_ids_str = await redis_client.zrange(feed_key, offset, end_index)
    news_ids = [int(nid) for nid in cached_ids_str]

    if not news_ids:
        seen_ids_str = await redis_client.smembers(seen_key)
        seen_ids = [int(nid) for nid in seen_ids_str]
        fetched_ids = []

        if active_vector:
            must_not_conditions = [qmodels.HasIdCondition(has_id=seen_ids)] if seen_ids else []
            try:
                search_result = await qdrant_client.search(
                    collection_name="news_articles",
                    query_vector=active_vector,
                    query_filter=qmodels.Filter(must_not=must_not_conditions),
                    limit=200
                )
                qdrant_score = {int(hit.id): hit.score for hit in search_result}
                rescored_ids = await _rescore_and_sort_news(db, qdrant_score)
                fetched_ids = rescored_ids[:50]
            except Exception as e:
                print(f"Qdrant/Rescoring Error: {e}")
                fetched_ids = []

        if len(fetched_ids) < 50:
            exclude_ids = list(set(seen_ids + fetched_ids))
            fallback_needed = 50 - len(fetched_ids)

            fallback_ids = await get_fallback_news_ids(db, exclude_ids, limit=fallback_needed)
            if fallback_ids:
                fetched_ids.extend(fallback_ids)

        if not fetched_ids:
            return []

        zadd_data = {str(nid): score for score, nid in enumerate(fetched_ids)}
        await redis_client.zadd(feed_key, zadd_data)

        if not fetched_ids:
            return []

        zadd_data = {str(nid): score for score, nid in enumerate(fetched_ids)}
        await redis_client.zadd(feed_key, zadd_data)
        await redis_client.expire(feed_key, FEED_CACHE_TTL)
        news_ids = fetched_ids[offset: offset + limit]
    else:
        await redis_client.expire(feed_key, FEED_CACHE_TTL)

    if not news_ids:
        return []

    sorted_news = await get_news_by_ids_sorted(db, news_ids)

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