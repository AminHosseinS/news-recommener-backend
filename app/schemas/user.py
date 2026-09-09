from pydantic import BaseModel, ConfigDict, Field
from typing import List

class UserFavoriteTagsRequest(BaseModel):
    tags: List[str] = Field(default=[], max_length=5)


class UserFavoriteTagsResponse(BaseModel):
    tags: List[str] = []

    model_config = ConfigDict(from_attributes=True)