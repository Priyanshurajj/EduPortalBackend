from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.classroom import Classroom, student_classroom
from app.models.chat import ChatMessage
from app.schemas.chat import ChatMessageResponse, ChatHistoryResponse
from app.core.security import get_current_user

router = APIRouter(prefix="/api/classrooms", tags=["Chat"])


def is_user_in_classroom(db: Session, user_id: int, classroom_id: int) -> bool:
    """Check if user is teacher or enrolled student in the classroom."""
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        return False
    
    # Check if user is the teacher
    if classroom.teacher_id == user_id:
        return True
    
    # Check if user is an enrolled student
    enrollment = db.execute(
        student_classroom.select().where(
            (student_classroom.c.student_id == user_id) &
            (student_classroom.c.classroom_id == classroom_id)
        )
    ).first()
    
    return enrollment is not None


@router.get("/{classroom_id}/messages", response_model=ChatHistoryResponse)
async def get_chat_history(
    classroom_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get paginated chat history for a classroom.
    Only accessible by the teacher or enrolled students.
    """
    # Check if classroom exists
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found"
        )
    
    # Check authorization
    if not is_user_in_classroom(db, current_user.id, classroom_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this classroom's chat"
        )
    
    # Get total message count
    total = db.query(ChatMessage).filter(ChatMessage.classroom_id == classroom_id).count()
    
    # Get paginated messages (newest first, then reverse for display)
    offset = (page - 1) * page_size
    messages = db.query(ChatMessage).filter(
        ChatMessage.classroom_id == classroom_id
    ).order_by(
        ChatMessage.sent_at.desc()
    ).offset(offset).limit(page_size).all()
    
    # Reverse to get chronological order
    messages = list(reversed(messages))
    
    # Convert to response format
    message_responses = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        message_responses.append(ChatMessageResponse(
            id=msg.id,
            classroom_id=msg.classroom_id,
            sender_id=msg.sender_id,
            sender_name=sender.full_name if sender else "Unknown",
            sender_role=sender.role.value if sender else "unknown",
            content=msg.content,
            sent_at=msg.sent_at
        ))
    
    has_more = offset + page_size < total
    
    return ChatHistoryResponse(
        messages=message_responses,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more
    )


@router.get("/{classroom_id}/messages/recent", response_model=list[ChatMessageResponse])
async def get_recent_messages(
    classroom_id: int,
    limit: int = Query(20, ge=1, le=100),
    before_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent messages for a classroom.
    Optionally get messages before a specific message ID for infinite scroll.
    """
    # Check if classroom exists
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found"
        )
    
    # Check authorization
    if not is_user_in_classroom(db, current_user.id, classroom_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this classroom's chat"
        )
    
    # Build query
    query = db.query(ChatMessage).filter(ChatMessage.classroom_id == classroom_id)
    
    if before_id:
        query = query.filter(ChatMessage.id < before_id)
    
    # Get messages (newest first)
    messages = query.order_by(ChatMessage.sent_at.desc()).limit(limit).all()
    
    # Reverse to get chronological order
    messages = list(reversed(messages))
    
    # Convert to response format
    message_responses = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        message_responses.append(ChatMessageResponse(
            id=msg.id,
            classroom_id=msg.classroom_id,
            sender_id=msg.sender_id,
            sender_name=sender.full_name if sender else "Unknown",
            sender_role=sender.role.value if sender else "unknown",
            content=msg.content,
            sent_at=msg.sent_at
        ))
    
    return message_responses
