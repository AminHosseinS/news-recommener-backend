from fastapi import APIRouter

from app.router.endpoints import auth, feed, profile

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(feed.router, prefix="/feed", tags=["Feed"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])