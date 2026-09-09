from datetime import datetime

from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Literal

ActionType = Literal[
    "like",
    "share",
    "read_more",
    "bookmark",
    "hide"
]

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

class InteractionItem(BaseModel):
    news_id: int
    actions: List[ActionType] = []
    duration: int = 0  # second

class TrackImpressionRequest(BaseModel):
    interactions: List[InteractionItem]


class NewsSearchResponse(BaseModel):
    id: int
    title: str
    image_url: Optional[str] = None
    ai_summary: Optional[str] = None
    tags: List[str] = []
    pub_date: datetime

    model_config = ConfigDict(from_attributes=True)