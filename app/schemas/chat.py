import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionHistoryOut(BaseModel):
    session_id: uuid.UUID
    messages: list[MessageOut]


# SSE event payloads
class DeltaEvent(BaseModel):
    text: str


class DoneEvent(BaseModel):
    session_id: uuid.UUID


class FailedEvent(BaseModel):
    error: str


class HeartbeatEvent(BaseModel):
    status: str = "alive"
