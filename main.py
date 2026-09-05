from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.database.qdrant_setup import init_qdrant_collections
from app.router.api_router import api_router
from app.database import qdrant


@asynccontextmanager
async def lifespan(app: FastAPI):
    qdrant.qdrant_client = qdrant.init_qdrant_client()

    await init_qdrant_collections(
        client=qdrant.qdrant_client,
        recreate_if_exists=False # Only on dev should be True for dropping qdrant db
    )

    yield

    if qdrant.qdrant_client:
        await qdrant.qdrant_client.close()

app = FastAPI(
    title="News Recommender API",
    description="AI-Powered personalized news recommendation system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")