"""
Summary Service
Handles summary generation and RAG-based chat using Google Gemini.
"""

from typing import List, Optional
import google.generativeai as genai
from app.core.config import settings


class SummaryService:
    """Service for generating summaries and chat responses using Gemini."""
    
    SUMMARY_PROMPT = """You are an expert summarizer. Analyze the following content and provide:

1. **Summary**: A concise summary (2-3 paragraphs) capturing the main ideas
2. **Key Points**: A bullet list of the most important points (5-10 items)
3. **Topics Covered**: A brief list of main topics/themes

Content:
{content}

Provide a well-structured summary that captures the essential information. Use markdown formatting."""

    RAG_CHAT_PROMPT = """You are a helpful study assistant. Answer the user's question based ONLY on the provided context from the uploaded material.

**Important Instructions:**
- Only use information from the provided context
- If the answer is not in the context, say "I don't have enough information in the provided material to answer that question."
- Be concise but thorough
- Use markdown formatting for better readability
- If relevant, quote specific parts from the context

**Context from the uploaded material:**
{context}

**User Question:** {question}

**Answer:**"""

    def __init__(self):
        self._configured = False
        self._model = None
        self._configure_api()
    
    def _configure_api(self):
        """Configure the Gemini API."""
        if settings.GOOGLE_API_KEY:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            self._model = genai.GenerativeModel(settings.GEMINI_MODEL)
            self._configured = True
        else:
            self._configured = False
    
    def is_configured(self) -> bool:
        """Check if the service is properly configured."""
        return self._configured
    
    async def generate_summary(self, content: str) -> str:
        """
        Generate a summary for the provided content.
        
        Args:
            content: The text content to summarize
            
        Returns:
            Generated summary text
            
        Raises:
            ValueError: If API is not configured or generation fails
        """
        if not self._configured:
            raise ValueError("Gemini API key not configured. Set GOOGLE_API_KEY in environment.")
        
        # Truncate content if too long (Gemini has token limits)
        max_chars = 100000  # ~25k tokens
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated due to length...]"
        
        try:
            prompt = self.SUMMARY_PROMPT.format(content=content)
            response = await self._model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                )
            )
            return response.text
        except Exception as e:
            raise ValueError(f"Failed to generate summary: {str(e)}")
    
    async def generate_chat_response(
        self,
        question: str,
        context_chunks: List[str],
        chat_history: Optional[List[dict]] = None
    ) -> str:
        """
        Generate a RAG-based chat response.
        
        Args:
            question: The user's question
            context_chunks: Relevant text chunks from RAG retrieval
            chat_history: Optional previous chat messages
            
        Returns:
            Generated response text
        """
        if not self._configured:
            raise ValueError("Gemini API key not configured. Set GOOGLE_API_KEY in environment.")
        
        # Format context
        context = "\n\n---\n\n".join(context_chunks)
        
        # Build the prompt
        prompt = self.RAG_CHAT_PROMPT.format(
            context=context,
            question=question
        )
        
        # Add chat history if provided
        if chat_history:
            history_text = "\n\n**Previous conversation:**\n"
            for msg in chat_history[-5:]:  # Last 5 messages
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_text += f"{role}: {msg.get('content', '')}\n"
            prompt = history_text + "\n" + prompt
        
        try:
            response = await self._model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=1024,
                )
            )
            return response.text
        except Exception as e:
            raise ValueError(f"Failed to generate response: {str(e)}")
    
    def generate_summary_sync(self, content: str) -> str:
        """
        Synchronous version of generate_summary.
        
        Args:
            content: The text content to summarize
            
        Returns:
            Generated summary text
        """
        if not self._configured:
            raise ValueError("Gemini API key not configured. Set GOOGLE_API_KEY in environment.")
        
        max_chars = 100000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated due to length...]"
        
        try:
            prompt = self.SUMMARY_PROMPT.format(content=content)
            response = self._model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                )
            )
            return response.text
        except Exception as e:
            raise ValueError(f"Failed to generate summary: {str(e)}")
    
    def generate_chat_response_sync(
        self,
        question: str,
        context_chunks: List[str],
        chat_history: Optional[List[dict]] = None
    ) -> str:
        """
        Synchronous version of generate_chat_response.
        """
        if not self._configured:
            raise ValueError("Gemini API key not configured. Set GOOGLE_API_KEY in environment.")
        
        context = "\n\n---\n\n".join(context_chunks)
        prompt = self.RAG_CHAT_PROMPT.format(
            context=context,
            question=question
        )
        
        if chat_history:
            history_text = "\n\n**Previous conversation:**\n"
            for msg in chat_history[-5:]:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_text += f"{role}: {msg.get('content', '')}\n"
            prompt = history_text + "\n" + prompt
        
        try:
            response = self._model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=1024,
                )
            )
            return response.text
        except Exception as e:
            raise ValueError(f"Failed to generate response: {str(e)}")


# Global summary service instance
_summary_service: Optional[SummaryService] = None


def get_summary_service() -> SummaryService:
    """Get or create the global summary service instance."""
    global _summary_service
    if _summary_service is None:
        _summary_service = SummaryService()
    return _summary_service
