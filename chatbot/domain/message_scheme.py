import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    text: str
    nickname: str
    user_uuid: uuid.UUID

    ai_generated: bool
    ended_conversession: bool
    model_config = ConfigDict(from_attributes=True)


class MessageItem(MessageBase):
    id: int
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

