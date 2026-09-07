import math
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import numpy as np

from fastapi import BackgroundTasks
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
import redis.asyncio as redis
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import session as SessionLocal
from app.models.news import News
from app.models import User
from app.schemas.feed import TrackImpressionRequest

FEED_CACHE_TTL = 30 * 60
SEEN_NEWS_TTL = 7 * 24 * 3600
VECTOR_CACHE_TTL = 7 * 24 * 3600

def calculate_time_decay(age_hours: float, validity: str) -> float:
    if validity == "breaking-news":
        if age_hours > 24: return 0.0
        return math.exp(- (math.log(2) / 6.0) * age_hours)
    elif validity == "daily-news":
        if age_hours > 90: return 0.0
        return math.exp(- (math.log(2) / 24.0) * age_hours)
    return 1.0  # evergreen

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

async def bg_process_interactions(
        user_id: uuid.UUID,
        request: TrackImpressionRequest,
        redis_client: redis.Redis,
        qdrant_client: AsyncQdrantClient
):
    if not request.interactions:
        return

    alpha_scores: Dict[int, float] = {}
    seen_ids = []
    for item in request.interactions:
        seen_ids.append(item.news_id)
        alpha = 0.0

        if "hide" in item.actions:
            alpha = -1.0
        else:
            if "like" in item.actions: alpha += 0.4
            if "bookmark" in item.actions: alpha += 0.4
            if "share" in item.actions: alpha += 0.3
            if "read_more" in item.actions: alpha += 0.2

            if item.duration > 10:
                duration_score = (item.duration // 10) * 0.1
                alpha += min(0.3, duration_score)

            if not item.actions and item.duration <= 3:
                alpha -= 0.05

        alpha = max(-1.0, min(1.0, alpha))

        if alpha != 0.0:
            alpha_scores[item.news_id] = alpha

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

        current_vector = None
        if cached_vector:
            current_vector = json.loads(cached_vector)
        else:
            if user and user.interest_vector:
                current_vector = user.interest_vector
            else:
                return

        interacted_news_ids = list(alpha_scores.keys())

        stmt_tags = select(News.id,News.tags).where(News.id.in_(interacted_news_ids))
        res_tags = await db.execute(stmt_tags)
        news_tags_map = {row.id: set(row.tags or []) for row in res_tags.all()}

        user_tags = set(user.favorite_tags or [])

        points = await qdrant_client.retrieve(
            collection_name="news_articles",
            ids=interacted_news_ids,
            with_vectors=True
        )

        new_vector = np.array(current_vector, dtype=np.float32)

        for point in points:
            alpha = alpha_scores.get(point.id, 0)
            news_vector = np.array(point.vector, dtype=np.float32)

            article_tags = news_tags_map.get(point.id, set())

            if user_tags and article_tags and user_tags.intersection(article_tags):
                gamma = 0.30
            elif user_tags:
                gamma = 0.08
            else:
                gamma = 0.15

            new_vector = (1 - gamma) * new_vector + (gamma * alpha * news_vector)

        norm = np.linalg.norm(new_vector)
        if norm > 0:
            new_vector = new_vector / norm

        new_vector_list = new_vector.tolist()

        await redis_client.set(vector_key, json.dumps(new_vector_list), ex=VECTOR_CACHE_TTL)

        feed_key = f"feed:web:{user_id}"
        if not await redis_client.exists(feed_key):
            return

        all_seen_str = await redis_client.smembers(seen_key)
        all_seen_ids = [int(x) for x in all_seen_str]

        must_not_conditions = [qmodels.HasIdCondition(has_id=all_seen_ids)] if all_seen_ids else []

        search_result = await qdrant_client.search(
            collection_name="news_articles",
            query_vector=new_vector,
            query_filter=qmodels.Filter(must_not=must_not_conditions),
            limit=30
        )

        qdrant_score = {int(hit.id): hit.score for hit in search_result}
        if not qdrant_score:
            return

        stmt = select(News.id, News.pub_date, News.time_validity).where(
            News.id.in_(qdrant_score.keys()),
            News.status == "READY"
        )
        res = await db.execute(stmt)
        meta_rows = res.all()

        now_utc = datetime.now(timezone.utc)
        rescored_news = []
        for row in meta_rows:
            age_hours = (now_utc - row.pub_date).total_seconds() / 3600
            decay_multiplier = calculate_time_decay(age_hours, row.time_validity)
            final_score = qdrant_score[row.id] * decay_multiplier
            if final_score > 0.1:
                rescored_news.append((final_score, row.id))

        rescored_news.sort(key=lambda x: x[0], reverse=True)
        top_new_ids = [item[1] for item in rescored_news[:10]]

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
            new_vector = json.loads(cached_vector_str)
            user.interest_vector = new_vector
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
        now_utc = datetime.now(timezone.utc)

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

                if qdrant_score:
                    stmt = select(News.id, News.pub_date, News.time_validity).where(
                        News.id.in_(qdrant_score.keys()),
                        News.status == "READY"
                    )
                    res = await db.execute(stmt)
                    meta_rows = res.all()

                    rescored_news = []
                    for row in meta_rows:
                        age_hours = (now_utc - row.pub_date).total_seconds() / 3600
                        decay_multiplier = calculate_time_decay(age_hours, row.time_validity)
                        final_score = qdrant_score[row.id] * decay_multiplier
                        if final_score > 0.1:
                            rescored_news.append((final_score, row.id))

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
                News.status == "READY"
            ).order_by(News.pub_date.desc()).limit(50)

            if seen_ids:
                stmt = stmt.where(News.id.notin_(seen_ids))

            res = await db.execute(stmt)
            fetched_ids = res.scalars().all()

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

    stmt = select(News).where(
        News.id.in_(news_ids),
        News.status == "READY"
    )
    res = await db.execute(stmt)
    news_rows = res.scalars().all()

    news_dict = {n.id: n for n in news_rows}
    sorted_news = [news_dict[nid] for nid in news_ids if nid in news_dict]

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