from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


class UserFavoriteTagsRequest(BaseModel):
    tags: List[str] = Field(default=[], max_length=5)


class UserFavoriteTagsResponse(BaseModel):
    tags: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class UserProfileResponse(BaseModel):
    phone_number: Optional[str] = None
    is_connected_to_bale: bool = False

    model_config = ConfigDict(from_attributes=True)