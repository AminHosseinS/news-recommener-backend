from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database.config import settings

engine = create_async_engine(
    url=settings.DB_URL,
    echo=True,
)

session =  async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session() as db:
        try:
            yield db
        finally:
            await db.close()