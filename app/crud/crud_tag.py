from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tag import Tag

async def get_tags_by_slugs(db: AsyncSession, tag_names: list[str]) -> Sequence[Tag]:
    result = await db.execute(select(Tag).where(Tag.slug.in_(tag_names)))
    return result.scalars().all()