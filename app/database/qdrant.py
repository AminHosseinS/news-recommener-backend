from typing import AsyncGenerator

from qdrant_client import AsyncQdrantClient

from app.core.config import qdrant_settings

qdrant_client : AsyncQdrantClient | None = None

def init_qdrant_client():
    if qdrant_settings.QDRANT_URL:
        return AsyncQdrantClient(url=qdrant_settings.QDRANT_URL)

    return AsyncQdrantClient(path=qdrant_settings.QDRANT_LOCAL_PATH)

async def get_qdrant() -> AsyncGenerator[AsyncQdrantClient, None]:
    if qdrant_client is None:
        raise RuntimeError("Qdrant client is not initialized")
    yield qdrant_client