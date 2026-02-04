from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.connection import Base


class ChatMessage(Base):
    """Chat message model for classroom discussions."""
    
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    classroom_id = Column(Integer, ForeignKey('classrooms.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = Column(Text, nullable=False)
    sent_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    
    # Relationships
    classroom = relationship("Classroom", backref="messages")
    sender = relationship("User", backref="chat_messages")
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, classroom_id={self.classroom_id}, sender_id={self.sender_id})>"
