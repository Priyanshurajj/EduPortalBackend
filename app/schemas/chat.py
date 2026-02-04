from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChatMessageCreate(BaseModel):
    """Schema for creating a new chat message."""
    content: str = Field(..., min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""
    id: int
    classroom_id: int
    sender_id: int
    sender_name: str
    sender_role: str
    content: str
    sent_at: datetime

    class Config:
        from_attributes = True


class ChatMessageBroadcast(BaseModel):
    """Schema for broadcasting chat message via Socket.IO."""
    id: int
    classroom_id: int
    sender_id: int
    sender_name: str
    sender_role: str
    content: str
    sent_at: str  # ISO format string for JSON serialization


class ChatHistoryResponse(BaseModel):
    """Schema for paginated chat history response."""
    messages: list[ChatMessageResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
