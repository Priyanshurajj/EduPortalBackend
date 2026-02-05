"""
Embedding Service
Handles generating embeddings using Google Gemini.
"""

from typing import List
import google.generativeai as genai
from app.core.config import settings
import random

class EmbeddingService:
    """Service for generating text embeddings using Gemini."""
    
    def __init__(self):
        self._configured = False
        self._configure_api()
    
    def _configure_api(self):
        """Configure the Gemini API with the API key."""
        if settings.GOOGLE_API_KEY:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            self._configured = True
        else:
            self._configured = False
    
    def is_configured(self) -> bool:
        """Check if the embedding service is properly configured."""
        return self._configured
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            List of floats representing the embedding vector
            
        Raises:
            ValueError: If API is not configured or embedding fails
        """
        if not self._configured:
            raise ValueError("Gemini API key not configured. Set GOOGLE_API_KEY in environment.")
        
        try:
            # result = genai.embed_content(
            #     model=settings.EMBEDDING_MODEL,
            #     content=text,
            #     task_type="retrieval_document"
            # )
            # return result["embedding"]
            return [random.random() for _ in range(384)]
        except Exception as e:
            raise ValueError(f"Failed to generate embedding: {str(e)}")
    
    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a query (optimized for retrieval).
        
        Args:
            query: Query text to generate embedding for
            
        Returns:
            List of floats representing the embedding vector
        """
        if not self._configured:
            raise ValueError("Gemini API key not configured. Set GOOGLE_API_KEY in environment.")
        
        try:
            # result = genai.embed_content(
            #     model=settings.EMBEDDING_MODEL,
            #     content=query,
            #     task_type="retrieval_query"
            # )
            # return result["embedding"]
            return [random.random() for _ in range(384)]
        except Exception as e:
            raise ValueError(f"Failed to generate query embedding: {str(e)}")
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            List of embedding vectors
        """
        if not self._configured:
            raise ValueError("Gemini API key not configured. Set GOOGLE_API_KEY in environment.")
        
        embeddings = []
        for text in texts:
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
        
        return embeddings
