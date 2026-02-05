"""
AI Router
Handles AI-powered summarization and RAG-based chat endpoints.
"""

from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Optional

from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.schemas.ai import (
    SourceType,
    SummarizeResponse,
    ChatRequest,
    ChatResponse,
    SessionInfo,
    SessionDeleteResponse,
)
from app.services.content_loader import ContentLoader
from app.services.rag_service import get_rag_service, RAGService
from app.services.summary_service import get_summary_service, SummaryService

router = APIRouter(prefix="/api/ai", tags=["AI Study Assistant"])


def get_content_loader() -> ContentLoader:
    """Dependency for content loader."""
    return ContentLoader()


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    summary="Summarize uploaded material",
    description="Upload content (URL, text, PDF, or text file) and get an AI-generated summary. Creates a session for follow-up chat.",
)
async def summarize_material(
    source_type: SourceType = Form(..., description="Type of source: url, text, pdf, or txt"),
    content: Optional[str] = Form(None, description="URL or text content (for url/text types)"),
    title: Optional[str] = Form(None, description="Optional title for the content"),
    file: Optional[UploadFile] = File(None, description="File upload (for pdf/txt types)"),
    current_user: User = Depends(get_current_user),
    content_loader: ContentLoader = Depends(get_content_loader),
    rag_service: RAGService = Depends(get_rag_service),
    summary_service: SummaryService = Depends(get_summary_service),
):
    """
    Process uploaded material and generate a summary.
    
    - **source_type**: Type of content being uploaded (url, text, pdf, txt)
    - **content**: URL or raw text (required for url/text types)
    - **title**: Optional title for the material
    - **file**: File upload (required for pdf/txt types)
    
    Returns a session_id that can be used for follow-up chat questions.
    """
    # Only students can use this feature
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature is only available for students"
        )
    
    # Check if AI services are configured
    if not summary_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured. Please set GOOGLE_API_KEY in environment."
        )
    
    try:
        # Extract content based on source type
        if source_type == SourceType.URL:
            if not content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="URL is required for url source type"
                )
            extracted_text, extracted_title = await content_loader.load_from_url(content)
            
        elif source_type == SourceType.TEXT:
            if not content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Text content is required for text source type"
                )
            extracted_text, extracted_title = content_loader.extract_from_raw_text(content, title)
            
        elif source_type == SourceType.PDF:
            if not file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PDF file is required for pdf source type"
                )
            file_content = await file.read()
            extracted_text, extracted_title = content_loader.extract_from_pdf(BytesIO(file_content))
            
        elif source_type == SourceType.TXT:
            if not file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Text file is required for txt source type"
                )
            file_content = await file.read()
            extracted_text, extracted_title = content_loader.extract_from_text_file(
                file_content, 
                file.filename or "document.txt"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported source type: {source_type}"
            )
        
        # Use provided title if available
        final_title = title or extracted_title
        
        # Validate extracted content
        if not extracted_text or len(extracted_text.strip()) < 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Extracted content is too short. Please provide more substantial content."
            )
        
        # Create RAG session
        session_id = rag_service.create_session(
            text=extracted_text,
            title=final_title,
            source_type=source_type.value
        )
        
        # Generate summary
        summary = await summary_service.generate_summary(extracted_text)
        
        # Get session info
        session_info = rag_service.get_session_info(session_id)
        
        return SummarizeResponse(
            session_id=session_id,
            summary=summary,
            source_type=source_type.value,
            title=final_title,
            chunk_count=session_info.get("chunk_count", 0),
            word_count=content_loader.get_word_count(extracted_text)
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process content: {str(e)}"
        )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with uploaded material",
    description="Ask questions about the uploaded material using RAG-based retrieval.",
)
async def chat_with_material(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
    summary_service: SummaryService = Depends(get_summary_service),
):
    """
    Ask questions about the uploaded material.
    
    - **session_id**: Session ID from the summarize endpoint
    - **message**: Your question about the material
    
    Returns an AI-generated response based on the uploaded content.
    """
    # Only students can use this feature
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature is only available for students"
        )
    
    # Check if session exists
    if not rag_service.session_exists(request.session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found. Please upload material first."
        )
    
    try:
        # Query RAG for relevant chunks
        results = rag_service.query(
            session_id=request.session_id,
            query_text=request.message
        )
        
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No relevant content found for your question."
            )
        
        # Extract text from results
        context_chunks = [r["text"] for r in results]
        
        # Generate response
        response = await summary_service.generate_chat_response(
            question=request.message,
            context_chunks=context_chunks
        )
        
        # Return response with source excerpts
        sources = [chunk[:200] + "..." if len(chunk) > 200 else chunk for chunk in context_chunks[:3]]
        
        return ChatResponse(
            response=response,
            sources=sources
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate response: {str(e)}"
        )


@router.get(
    "/session/{session_id}",
    response_model=SessionInfo,
    summary="Get session information",
    description="Get information about an active AI session.",
)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Get information about a specific session."""
    # Only students can use this feature
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature is only available for students"
        )
    
    session_info = rag_service.get_session_info(session_id)
    
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return SessionInfo(
        session_id=session_id,
        title=session_info.get("title", "Unknown"),
        source_type=session_info.get("source_type", "unknown"),
        chunk_count=session_info.get("chunk_count", 0),
        word_count=session_info.get("word_count", 0)
    )


@router.delete(
    "/session/{session_id}",
    response_model=SessionDeleteResponse,
    summary="Delete a session",
    description="Delete an AI session and clear its data.",
)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Delete a session and its associated data."""
    # Only students can use this feature
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature is only available for students"
        )
    
    deleted = rag_service.delete_session(session_id)
    
    if deleted:
        return SessionDeleteResponse(
            success=True,
            message="Session deleted successfully"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
