"""
Text Processor Service
Handles chunking text for embedding and RAG operations.
"""

from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.core.config import settings


class TextProcessor:
    """Service for processing and chunking text for RAG."""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks suitable for embedding.
        
        Args:
            text: The text to chunk
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []
        
        chunks = self.splitter.split_text(text)
        
        # Filter out empty or whitespace-only chunks
        chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
        
        return chunks
    
    def chunk_text_with_metadata(self, text: str, source: str = "unknown") -> List[dict]:
        """
        Split text into chunks with metadata.
        
        Args:
            text: The text to chunk
            source: Source identifier for the text
            
        Returns:
            List of dicts with 'text', 'source', and 'chunk_index' keys
        """
        chunks = self.chunk_text(text)
        
        return [
            {
                "text": chunk,
                "source": source,
                "chunk_index": i,
                "total_chunks": len(chunks)
            }
            for i, chunk in enumerate(chunks)
        ]
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).
        Gemini uses ~4 characters per token on average.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def truncate_to_token_limit(self, text: str, max_tokens: int = 30000) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            
        Returns:
            Truncated text
        """
        estimated_chars = max_tokens * 4
        if len(text) <= estimated_chars:
            return text
        return text[:estimated_chars] + "..."
