from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

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