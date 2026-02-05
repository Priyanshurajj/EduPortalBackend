"""
Pydantic schemas for AI/RAG endpoints.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Enum for content source types."""
    URL = "url"
    TEXT = "text"
    PDF = "pdf"
    TXT = "txt"


class SummarizeRequest(BaseModel):
    """Request schema for URL or text summarization."""
    source_type: SourceType = Field(..., description="Type of source: url, text, pdf, or txt")
    content: Optional[str] = Field(None, description="URL or text content (for url/text types)")
    title: Optional[str] = Field(None, description="Optional title for the content")


class SummarizeResponse(BaseModel):
    """Response schema for summarization."""
    session_id: str = Field(..., description="Session ID for follow-up chat")
    summary: str = Field(..., description="Generated summary")
    source_type: str = Field(..., description="Type of source processed")
    title: str = Field(..., description="Title of the content")
    chunk_count: int = Field(..., description="Number of chunks created for RAG")
    word_count: int = Field(..., description="Approximate word count of content")


class ChatRequest(BaseModel):
    """Request schema for RAG chat."""
    session_id: str = Field(..., description="Session ID from summarize response")
    message: str = Field(..., min_length=1, max_length=2000, description="User's question")


class ChatResponse(BaseModel):
    """Response schema for RAG chat."""
    response: str = Field(..., description="AI-generated response")
    sources: List[str] = Field(default=[], description="Relevant source excerpts used")


class SessionInfo(BaseModel):
    """Schema for session information."""
    session_id: str
    title: str
    source_type: str
    chunk_count: int
    word_count: int


class SessionDeleteResponse(BaseModel):
    """Response schema for session deletion."""
    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: str
