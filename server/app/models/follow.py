"""follows collection."""
from datetime import datetime
from typing import TypedDict


class FollowDocument(TypedDict, total=False):
    _id: object
    follower_id: str
    followee_id: str
    created_at: datetime
