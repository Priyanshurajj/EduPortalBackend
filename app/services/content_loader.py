"""
Content Loader Service
Handles loading content from various sources: URLs, PDFs, and text files.
"""

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from typing import Optional, Tuple
from io import BytesIO
import re


class ContentLoader:
    """Service for loading and extracting text content from various sources."""
    
    def __init__(self):
        self.supported_url_schemes = ["http", "https"]
        self.max_url_content_length = 100000  # ~100KB of text
    
    async def load_from_url(self, url: str) -> Tuple[str, str]:
        """
        Load and extract text content from a URL.
        
        Args:
            url: The URL to fetch content from
            
        Returns:
            Tuple of (extracted_text, title)
            
        Raises:
            ValueError: If URL is invalid or content cannot be fetched
        """
        # Validate URL
        if not any(url.startswith(scheme) for scheme in ["http://", "https://"]):
            raise ValueError("Invalid URL. Must start with http:// or https://")
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "")
                
                # Handle PDF URLs
                if "application/pdf" in content_type:
                    return self.extract_from_pdf(BytesIO(response.content))
                
                # Handle HTML content
                if "text/html" in content_type or not content_type:
                    return self._extract_from_html(response.text, url)
                
                # Handle plain text
                if "text/plain" in content_type:
                    return response.text[:self.max_url_content_length], self._extract_title_from_url(url)
                
                raise ValueError(f"Unsupported content type: {content_type}")
                
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch URL: {str(e)}")
    
    def _extract_from_html(self, html_content: str, url: str) -> Tuple[str, str]:
        """Extract text and title from HTML content."""
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extract title
        title = ""
        if soup.title:
            title = soup.title.string or ""
        if not title:
            title = self._extract_title_from_url(url)
        
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        # Try to find main content
        main_content = soup.find("main") or soup.find("article") or soup.find("body")
        
        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        
        # Clean up the text
        text = self._clean_text(text)
        
        return text[:self.max_url_content_length], title.strip()
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract a title from URL path."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if path:
            # Get last path segment
            title = path.split("/")[-1]
            # Remove file extension
            title = re.sub(r"\.\w+$", "", title)
            # Replace hyphens/underscores with spaces
            title = re.sub(r"[-_]", " ", title)
            return title.title()
        return parsed.netloc
    
    def extract_from_pdf(self, pdf_file: BytesIO) -> Tuple[str, str]:
        """
        Extract text content from a PDF file.
        
        Args:
            pdf_file: BytesIO object containing PDF data
            
        Returns:
            Tuple of (extracted_text, title)
        """
        try:
            reader = PdfReader(pdf_file)
            
            # Extract title from metadata
            title = ""
            if reader.metadata:
                title = reader.metadata.get("/Title", "") or ""
            
            # Extract text from all pages
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            text = "\n\n".join(text_parts)
            text = self._clean_text(text)
            
            if not title:
                # Try to extract title from first line
                first_line = text.split("\n")[0] if text else "PDF Document"
                title = first_line[:100] if len(first_line) > 100 else first_line
            
            return text, title.strip()
            
        except Exception as e:
            raise ValueError(f"Failed to extract PDF content: {str(e)}")
    
    def extract_from_text_file(self, file_content: bytes, filename: str) -> Tuple[str, str]:
        """
        Extract content from a text file.
        
        Args:
            file_content: Raw bytes of the text file
            filename: Original filename
            
        Returns:
            Tuple of (text_content, title)
        """
        try:
            # Try different encodings
            encodings = ["utf-8", "latin-1", "cp1252"]
            text = None
            
            for encoding in encodings:
                try:
                    text = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                raise ValueError("Could not decode text file with supported encodings")
            
            text = self._clean_text(text)
            
            # Extract title from filename
            title = re.sub(r"\.\w+$", "", filename)
            title = re.sub(r"[-_]", " ", title).title()
            
            return text, title
            
        except Exception as e:
            raise ValueError(f"Failed to read text file: {str(e)}")
    
    def extract_from_raw_text(self, text: str, title: Optional[str] = None) -> Tuple[str, str]:
        """
        Process raw text input.
        
        Args:
            text: Raw text content
            title: Optional title for the content
            
        Returns:
            Tuple of (cleaned_text, title)
        """
        cleaned_text = self._clean_text(text)
        
        if not title:
            # Extract title from first line or generate one
            first_line = cleaned_text.split("\n")[0] if cleaned_text else "Text Document"
            title = first_line[:50] if len(first_line) > 50 else first_line
            if len(first_line) > 50:
                title += "..."
        
        return cleaned_text, title
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\t+", " ", text)
        
        # Remove non-printable characters (except newlines)
        text = "".join(char for char in text if char.isprintable() or char in "\n\r")
        
        return text.strip()
    
    def get_word_count(self, text: str) -> int:
        """Get the word count of text."""
        return len(text.split())
