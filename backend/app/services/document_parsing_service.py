"""
Document Parsing Service.

Handles parsing various document formats and fetching content from URLs:
- PDF files (PyPDF2 + pdfplumber fallback)
- DOCX files (python-docx)
- Text files (TXT, MD with encoding detection)
- URLs (BeautifulSoup HTML parsing)
"""

import re
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Tuple
import requests
from fastapi import UploadFile

# PDF parsing
import PyPDF2
import pdfplumber

# DOCX parsing
from docx import Document

# HTML parsing
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# File type detection
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


class NoContentError(Exception):
    """Raised when URL fetch succeeds but no extractable content is found."""

    def __init__(self, message: str, meta_info: dict = None):
        super().__init__(message)
        self.meta_info = meta_info or {}


class DocumentParsingService:
    """Service for parsing documents and fetching URL content."""

    # Configuration
    MAX_FILE_SIZE_MB = 50
    ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.md', '.docx'}
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'text/plain',
        'text/markdown',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }

    # URL fetching config
    URL_FETCH_TIMEOUT = 10  # seconds
    MAX_REDIRECTS = 3

    # Blocked IPs for SSRF prevention
    BLOCKED_IP_PATTERNS = [
        r'^127\.',           # localhost
        r'^10\.',            # 10.0.0.0/8
        r'^172\.(1[6-9]|2[0-9]|3[01])\.', # 172.16.0.0/12
        r'^192\.168\.',      # 192.168.0.0/16
        r'^169\.254\.',      # link-local
        r'^::1$',            # IPv6 localhost
        r'^fc00:',           # IPv6 private
    ]

    def __init__(self):
        """Initialize the document parsing service."""
        pass

    def validate_file(self, file: UploadFile) -> Dict[str, any]:
        """
        Validate uploaded file.

        Checks:
        - File size (< 50MB)
        - File extension (.pdf, .txt, .md, .docx)
        - MIME type (if python-magic available)

        Args:
            file: FastAPI UploadFile object

        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'file_type': str,
                'size_mb': float,
                'error': str | None
            }
        """
        # Get file extension
        file_ext = Path(file.filename).suffix.lower()

        # Check extension
        if file_ext not in self.ALLOWED_EXTENSIONS:
            return {
                'valid': False,
                'file_type': file_ext,
                'size_mb': 0,
                'error': f"File type '{file_ext}' not allowed. Supported: {', '.join(self.ALLOWED_EXTENSIONS)}"
            }

        # Check file size (read in chunks to avoid loading entire file)
        file.file.seek(0, 2)  # Seek to end
        file_size_bytes = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        size_mb = file_size_bytes / (1024 * 1024)

        if size_mb > self.MAX_FILE_SIZE_MB:
            return {
                'valid': False,
                'file_type': file_ext,
                'size_mb': size_mb,
                'error': f"File too large ({size_mb:.1f}MB). Maximum size: {self.MAX_FILE_SIZE_MB}MB"
            }

        # Check MIME type if python-magic is available
        if HAS_MAGIC:
            file.file.seek(0)
            mime_type = magic.from_buffer(file.file.read(2048), mime=True)
            file.file.seek(0)

            if mime_type not in self.ALLOWED_MIME_TYPES:
                return {
                    'valid': False,
                    'file_type': file_ext,
                    'size_mb': size_mb,
                    'error': f"Invalid MIME type '{mime_type}'. File may be corrupted or mislabeled."
                }

        return {
            'valid': True,
            'file_type': file_ext,
            'size_mb': size_mb,
            'error': None
        }

    def parse_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF file.

        Uses PyPDF2 as primary parser, falls back to pdfplumber
        if PyPDF2 fails or extracts empty text.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text content

        Raises:
            Exception: If both parsers fail
        """
        text = ""

        # Try PyPDF2 first (faster)
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"PyPDF2 failed: {e}")
            text = ""

        # If PyPDF2 returned empty or very short text, try pdfplumber
        if len(text.strip()) < 100:
            try:
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as e:
                if not text:  # Only raise if we have no text at all
                    raise Exception(f"PDF parsing failed with both PyPDF2 and pdfplumber: {e}")

        if not text.strip():
            raise Exception("No text found in PDF. The file may contain only images or be password-protected.")

        return self.clean_text(text)

    def parse_docx(self, file_path: str) -> str:
        """
        Extract text from DOCX file.

        Simple extraction using python-docx library.
        Extracts paragraph text only (not tables or headers/footers).

        Args:
            file_path: Path to DOCX file

        Returns:
            Extracted text content

        Raises:
            Exception: If parsing fails
        """
        try:
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])

            if not text.strip():
                raise Exception("No text found in DOCX file.")

            return self.clean_text(text)
        except Exception as e:
            raise Exception(f"DOCX parsing failed: {e}")

    def parse_text_file(self, file_path: str) -> str:
        """
        Read plain text or markdown file.

        Attempts UTF-8 first, falls back to latin-1 if needed.

        Args:
            file_path: Path to text file

        Returns:
            File content

        Raises:
            Exception: If reading fails
        """
        # Try UTF-8 first
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            return self.clean_text(text)
        except UnicodeDecodeError:
            # Fall back to latin-1
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    text = f.read()
                return self.clean_text(text)
            except Exception as e:
                raise Exception(f"Text file reading failed: {e}")

    def fetch_url_content(self, url: str) -> Dict[str, str]:
        """
        Fetch and extract content from URL.

        Security features:
        - SSRF prevention (blocks internal IPs)
        - Timeout (10s)
        - Max redirects (3)
        - Only allows http/https

        Args:
            url: URL to fetch

        Returns:
            Dictionary with:
            {
                'url': str (final URL after redirects),
                'title': str (page title),
                'extracted_text': str (main content),
                'fetch_timestamp': str (ISO format)
            }

        Raises:
            ValueError: If URL is invalid or blocked
            Exception: If fetch fails
        """
        from datetime import datetime, timezone

        # Validate URL format
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            raise ValueError(f"Invalid URL scheme '{parsed_url.scheme}'. Only http and https are allowed.")

        # SSRF prevention: block internal IPs
        hostname = parsed_url.hostname
        if hostname:
            # Try to resolve hostname to IP
            try:
                import socket
                ip_address = socket.gethostbyname(hostname)

                for pattern in self.BLOCKED_IP_PATTERNS:
                    if re.match(pattern, ip_address):
                        raise ValueError(f"Access to internal IP addresses is blocked for security reasons.")
            except socket.gaierror:
                # Hostname couldn't be resolved, let requests handle it
                pass

        # Fetch URL
        try:
            # Create session to control redirects
            session = requests.Session()
            session.max_redirects = self.MAX_REDIRECTS

            response = session.get(
                url,
                timeout=self.URL_FETCH_TIMEOUT,
                allow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; ProductIntelligenceBot/1.0)'
                }
            )
            response.raise_for_status()
        except requests.Timeout:
            raise Exception(f"URL fetch timed out after {self.URL_FETCH_TIMEOUT}s")
        except requests.TooManyRedirects:
            raise Exception(f"Too many redirects (max {self.MAX_REDIRECTS})")
        except requests.RequestException as e:
            raise Exception(f"URL fetch failed: {str(e)}")

        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            raise Exception(f"Unsupported content type '{content_type}'. Only HTML and plain text are supported.")

        # Parse HTML
        soup = BeautifulSoup(response.text, 'lxml')

        # Extract title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()

        # Extract main content
        # Priority: <main>, <article>, <body>
        content_element = None
        for tag in ['main', 'article', 'body']:
            content_element = soup.find(tag)
            if content_element:
                break

        if not content_element:
            content_element = soup

        # Remove script and style tags
        for tag in content_element.find_all(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()

        # Extract text (preserve some structure with markdownify)
        extracted_text = md(str(content_element), heading_style="ATX")
        extracted_text = self.clean_text(extracted_text)

        if not extracted_text.strip():
            # Extract meta tags as fallback info
            meta_info = self._extract_meta_tags(soup)
            raise NoContentError(
                "This page appears to use JavaScript to render content (Single Page Application). "
                "The server cannot extract text from JavaScript-rendered pages.",
                meta_info=meta_info
            )

        return {
            'url': response.url,  # Final URL after redirects
            'title': title or parsed_url.hostname,
            'extracted_text': extracted_text,
            'fetch_timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }

    def _extract_meta_tags(self, soup: BeautifulSoup) -> dict:
        """Extract SEO meta tags from parsed HTML."""
        meta_info = {}

        # Title
        title_tag = soup.find('title')
        if title_tag:
            meta_info['title'] = title_tag.get_text().strip()

        # Description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            meta_info['description'] = desc_tag['content'].strip()

        # Keywords
        keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_tag and keywords_tag.get('content'):
            meta_info['keywords'] = keywords_tag['content'].strip()

        # Open Graph tags
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title and og_title.get('content'):
            meta_info['og_title'] = og_title['content'].strip()

        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content'):
            meta_info['og_description'] = og_desc['content'].strip()

        return meta_info

    def fetch_url_meta_only(self, url: str) -> dict:
        """
        Fetch only meta tags from a URL (for SPA/JavaScript-rendered pages).

        Returns:
            {
                'url': str,
                'title': str,
                'extracted_text': str (composed from meta tags),
                'fetch_timestamp': str,
                'source': 'meta_tags'
            }
        """
        from datetime import datetime, timezone

        # Validate URL format
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in ['http', 'https']:
            raise ValueError(f"Invalid URL scheme '{parsed_url.scheme}'. Only http and https are allowed.")

        # SSRF prevention: block internal IPs
        hostname = parsed_url.hostname
        if hostname:
            try:
                import socket
                ip_address = socket.gethostbyname(hostname)
                for pattern in self.BLOCKED_IP_PATTERNS:
                    if re.match(pattern, ip_address):
                        raise ValueError("Access to internal IP addresses is blocked for security reasons.")
            except socket.gaierror:
                pass

        # Fetch URL
        try:
            session = requests.Session()
            session.max_redirects = self.MAX_REDIRECTS
            response = session.get(
                url,
                timeout=self.URL_FETCH_TIMEOUT,
                allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; ProductIntelligenceBot/1.0)'}
            )
            response.raise_for_status()
        except requests.Timeout:
            raise Exception(f"URL fetch timed out after {self.URL_FETCH_TIMEOUT}s")
        except requests.TooManyRedirects:
            raise Exception(f"Too many redirects (max {self.MAX_REDIRECTS})")
        except requests.RequestException as e:
            raise Exception(f"URL fetch failed: {str(e)}")

        # Parse HTML and extract meta tags
        soup = BeautifulSoup(response.text, 'lxml')
        meta_info = self._extract_meta_tags(soup)

        if not meta_info:
            raise Exception("No meta tags found in URL")

        # Compose extracted text from meta tags
        text_parts = []
        title = meta_info.get('title') or meta_info.get('og_title', '')
        if title:
            text_parts.append(f"# {title}")

        description = meta_info.get('description') or meta_info.get('og_description', '')
        if description:
            text_parts.append(f"\n{description}")

        keywords = meta_info.get('keywords', '')
        if keywords:
            text_parts.append(f"\nKeywords: {keywords}")

        extracted_text = '\n'.join(text_parts)

        if not extracted_text.strip():
            raise Exception("No usable meta tag content found in URL")

        return {
            'url': response.url,
            'title': title or parsed_url.hostname,
            'extracted_text': extracted_text,
            'fetch_timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'source': 'meta_tags'
        }

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        - Remove excessive whitespace
        - Normalize newlines
        - Strip control characters

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove control characters except newlines and tabs
        text = ''.join(char for char in text if char.isprintable() or char in ['\n', '\t'])

        # Normalize whitespace
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)

        # Replace more than 2 consecutive newlines with 2
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def count_tokens_estimate(self, text: str) -> int:
        """
        Estimate token count.

        Uses simple heuristic: 1 token ≈ 4 characters
        (Good approximation for English text with Claude/GPT models)

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        return len(text) // 4
