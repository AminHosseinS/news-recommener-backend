import asyncio
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client import AsyncQdrantClient

from app.crud.crud_news import search_news_by_title, get_news_by_ids_sorted
from app.models.news import News
from app.core.embedding import generate_embedding

COLLECTION_NAME = "news_articles"


async def vector_search(qdrant: AsyncQdrantClient, query: str, limit: int = 10) -> List[int]:
    query_vector = await generate_embedding(query)

    search_result = await qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        with_payload=False
    )

    return [int(hit.id) for hit in search_result.points]


async def execute_search(db: AsyncSession, qdrant: AsyncQdrantClient, query: str, limit: int = 10) -> List[News]:
    query_cleaned = query.strip()
    if not query_cleaned:
        return []

    word_count = len(query_cleaned.split())
    final_ids = []

    if word_count <= 2:
        classic_task = search_news_by_title(db, query_cleaned, limit=limit)
        vector_task = vector_search(qdrant, query_cleaned, limit=limit)

        classic_ids, vector_ids = await asyncio.gather(classic_task, vector_task)

        seen = set()
        for nid in classic_ids + vector_ids:
            if nid not in seen:
                final_ids.append(nid)
                seen.add(nid)
    else:
        final_ids = await vector_search(qdrant, query_cleaned, limit=limit)

    if not final_ids:
        return []

    final_ids = final_ids[:limit]

    news_items = await get_news_by_ids_sorted(db, final_ids)

    return news_items