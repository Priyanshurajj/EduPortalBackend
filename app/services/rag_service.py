"""
RAG Service
Handles ChromaDB vector storage and retrieval for RAG operations.
"""

import uuid
from typing import List, Dict, Optional, Any
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.services.embedding_service import EmbeddingService
from app.services.text_processor import TextProcessor
from app.core.config import settings


class RAGService:
    """Service for RAG operations using ChromaDB."""
    
    def __init__(self):
        # Initialize ChromaDB client (in-memory for session-based storage)
        self.client = chromadb.Client(ChromaSettings(
            anonymized_telemetry=False,
            allow_reset=True
        ))
        
        self.embedding_service = EmbeddingService()
        self.text_processor = TextProcessor()
        
        # Track active sessions
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, text: str, title: str, source_type: str) -> str:
        """
        Create a new RAG session with the provided content.
        
        Args:
            text: The full text content to index
            title: Title of the content
            source_type: Type of source (url, pdf, txt, text)
            
        Returns:
            Session ID for future operations
        """
        session_id = str(uuid.uuid4())
        
        # Create a collection for this session
        collection = self.client.create_collection(
            name=f"session_{session_id.replace('-', '_')}",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Chunk the text
        chunks = self.text_processor.chunk_text(text)
        
        if not chunks:
            raise ValueError("No content to index. Text may be empty or too short.")
        
        # Generate embeddings and add to collection
        for i, chunk in enumerate(chunks):
            embedding = self.embedding_service.generate_embedding(chunk)
            collection.add(
                ids=[f"chunk_{i}"],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{"chunk_index": i, "source": source_type}]
            )
        
        # Store session metadata
        self._sessions[session_id] = {
            "collection_name": f"session_{session_id.replace('-', '_')}",
            "title": title,
            "source_type": source_type,
            "chunk_count": len(chunks),
            "word_count": self.text_processor.estimate_token_count(text) * 4 // 5,  # Rough word count
            "full_text": text[:5000]  # Store first 5000 chars for summary context
        }
        
        return session_id
    
    def query(
        self,
        session_id: str,
        query_text: str,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Query the RAG index for relevant chunks.
        
        Args:
            session_id: The session ID to query
            query_text: The query text
            top_k: Number of results to return (default from settings)
            
        Returns:
            List of relevant chunks with metadata
        """
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        top_k = top_k or settings.RAG_TOP_K
        
        # Get the collection
        collection_name = self._sessions[session_id]["collection_name"]
        collection = self.client.get_collection(collection_name)
        
        # Generate query embedding
        query_embedding = self.embedding_service.generate_query_embedding(query_text)
        
        # Query the collection
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count())
        )
        
        # Format results
        formatted_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append({
                    "text": doc,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                })
        
        return formatted_results
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            Session metadata or None if not found
        """
        return self._sessions.get(session_id)
    
    def get_session_context(self, session_id: str) -> str:
        """
        Get the stored context for a session (for summary generation).
        
        Args:
            session_id: The session ID
            
        Returns:
            The stored full text (truncated)
        """
        session = self._sessions.get(session_id)
        if session:
            return session.get("full_text", "")
        return ""
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its associated data.
        
        Args:
            session_id: The session ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        if session_id not in self._sessions:
            return False
        
        try:
            collection_name = self._sessions[session_id]["collection_name"]
            self.client.delete_collection(collection_name)
        except Exception:
            pass  # Collection may already be deleted
        
        del self._sessions[session_id]
        return True
    
    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        return session_id in self._sessions
    
    def get_all_sessions(self) -> List[str]:
        """Get all active session IDs."""
        return list(self._sessions.keys())
    
    def cleanup_all_sessions(self):
        """Clean up all sessions (for testing/maintenance)."""
        for session_id in list(self._sessions.keys()):
            self.delete_session(session_id)


# Global RAG service instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or create the global RAG service instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
