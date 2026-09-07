from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class NewsFeedItem(BaseModel):
    id: int
    title: str
    image_url: Optional[str]
    ai_summary: Optional[str]
    link: str
    tags: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class WebFeedResponse(BaseModel):
    data: List[NewsFeedItem]
    next_offset: Optional[int]

class TrackImpressionRequest(BaseModel):
    news_ids: List[int]