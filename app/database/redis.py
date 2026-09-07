import redis.asyncio as redis

from app.core.config import redis_settings

redis_pool = redis.ConnectionPool.from_url(
    redis_settings.REDIS_URL,
    decode_responses=True,
    max_connections=100,
)

async def get_redis():
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.close()
