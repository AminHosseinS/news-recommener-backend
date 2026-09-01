from typing import AsyncGenerator

from qdrant_client import AsyncQdrantClient

from app.database.config import settings

qdrant_client : AsyncQdrantClient | None = None

def init_qdrant_client():
    if settings.QDRANT_URL:
        return AsyncQdrantClient(url=settings.QDRANT_URL)

    return AsyncQdrantClient(path=settings.QDRANT_LOCAL_PATH)

async def get_qdrant() -> AsyncGenerator[AsyncQdrantClient, None]:
    if qdrant_client is None:
        raise RuntimeError("Qdrant client is not initialized")
    yield qdrant_client