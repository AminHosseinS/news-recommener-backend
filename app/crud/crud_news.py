from datetime import datetime, timedelta, timezone
from typing import List, Dict, Set, Any
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.news import News

async def get_news_tags_map(db: AsyncSession, news_ids: List[int]) -> Dict[int, Set[str]]:
    stmt_tags = select(News.id, News.tags).where(News.id.in_(news_ids))
    res_tags = await db.execute(stmt_tags)
    return {row.id: set(row.tags or []) for row in res_tags.all()}

async def get_news_meta_for_rescoring(db: AsyncSession, news_ids: List[int]) -> List[Any]:
    stmt = select(News.id, News.pub_date, News.time_validity).where(
        News.id.in_(news_ids),
        News.status == "READY"
    )
    res = await db.execute(stmt)
    return res.all()

async def get_fallback_news_ids(db: AsyncSession, seen_ids: List[int], limit: int = 50) -> List[int]:
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    stmt = select(News.id).where(
        or_(
            News.time_validity == "evergreen",
            News.pub_date >= three_days_ago,
        ),
        News.status == "READY"
    ).order_by(News.pub_date.desc()).limit(limit)

    if seen_ids:
        stmt = stmt.where(News.id.notin_(seen_ids))

    res = await db.execute(stmt)
    return list(res.scalars().all())

async def get_news_by_ids_sorted(db: AsyncSession, news_ids: List[int]) -> List[News]:
    stmt = select(News).where(
        News.id.in_(news_ids),
        News.status == "READY"
    )
    res = await db.execute(stmt)
    news_rows = res.scalars().all()
    news_dict = {n.id: n for n in news_rows}
    return [news_dict[nid] for nid in news_ids if nid in news_dict]

async def search_news_by_title(db: AsyncSession, query: str, limit: int = 10) -> List[int]:
    search_pattern = f"%{query}%"
    stmt = select(News.id).where(
        News.title.ilike(search_pattern),
        News.status == "READY"
    ).order_by(News.pub_date.desc()).limit(limit)

    res = await db.execute(stmt)
    return list(res.scalars().all())