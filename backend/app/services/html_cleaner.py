"""
HTML Cleaner Service for competitive analysis.

Cleans HTML content from web search results before injecting into LLM prompts.
This reduces token usage and improves accuracy by removing irrelevant content.

Features:
- Removes scripts, styles, navigation, ads
- Converts HTML to clean markdown
- Truncates to configurable character limits
- Preserves important content structure
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from markdownify import markdownify as md


class HTMLCleanerService:
    """
    Cleans HTML content to reduce token usage and improve LLM accuracy.

    Usage:
        cleaner = HTMLCleanerService()
        clean_content = cleaner.clean_html(raw_html)
        formatted_results = cleaner.clean_search_results(search_results)
    """

    # Tags to completely remove (content and tag)
    REMOVE_TAGS = [
        'script', 'style', 'nav', 'header', 'footer',
        'aside', 'iframe', 'noscript', 'svg', 'canvas',
        'form', 'button', 'input', 'select', 'textarea',
        'meta', 'link', 'head'
    ]

    # Tags that usually contain ads or navigation
    AD_PATTERNS = [
        re.compile(r'ad(s|vert)', re.IGNORECASE),
        re.compile(r'banner', re.IGNORECASE),
        re.compile(r'sponsor', re.IGNORECASE),
        re.compile(r'promo(tion)?', re.IGNORECASE),
        re.compile(r'sidebar', re.IGNORECASE),
        re.compile(r'menu', re.IGNORECASE),
        re.compile(r'newsletter', re.IGNORECASE),
        re.compile(r'popup', re.IGNORECASE),
        re.compile(r'modal', re.IGNORECASE),
        re.compile(r'cookie', re.IGNORECASE),
        re.compile(r'social', re.IGNORECASE),
    ]

    # Default limits
    DEFAULT_MAX_CHARS = 10000
    DEFAULT_MAX_CHARS_PER_RESULT = 3000

    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        max_chars_per_result: int = DEFAULT_MAX_CHARS_PER_RESULT
    ):
        """
        Initialize the HTML cleaner.

        Args:
            max_chars: Maximum total characters for combined output
            max_chars_per_result: Maximum characters per search result
        """
        self.max_chars = max_chars
        self.max_chars_per_result = max_chars_per_result

    def clean_html(
        self,
        html: str,
        max_chars: Optional[int] = None,
        preserve_links: bool = False
    ) -> str:
        """
        Clean HTML content and convert to markdown.

        Args:
            html: Raw HTML string
            max_chars: Override default max chars for this call
            preserve_links: If True, keep hyperlinks in output

        Returns:
            Cleaned markdown string
        """
        if not html or not html.strip():
            return ""

        max_chars = max_chars or self.max_chars

        try:
            # Parse HTML
            soup = BeautifulSoup(html, 'lxml')

            # Remove unwanted tags
            for tag_name in self.REMOVE_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Remove elements with ad-related classes/ids
            self._remove_ad_elements(soup)

            # Try to find main content
            main_content = self._find_main_content(soup)

            # Convert to markdown
            if preserve_links:
                markdown = md(str(main_content), heading_style="ATX")
            else:
                markdown = md(
                    str(main_content),
                    heading_style="ATX",
                    strip=['a']  # Remove links but keep text
                )

            # Clean up the markdown
            cleaned = self._clean_markdown(markdown)

            # Truncate if needed
            if len(cleaned) > max_chars:
                cleaned = self._smart_truncate(cleaned, max_chars)

            return cleaned

        except Exception as e:
            # If parsing fails, return empty or try basic text extraction
            print(f"[HTMLCleanerService] Error cleaning HTML: {e}")
            # Fallback: just strip HTML tags
            text = re.sub(r'<[^>]+>', ' ', html)
            text = self._clean_markdown(text)
            return text[:max_chars] if len(text) > max_chars else text

    def clean_search_results(
        self,
        results: List[Dict[str, Any]],
        max_chars_total: Optional[int] = None,
        max_chars_per_result: Optional[int] = None
    ) -> str:
        """
        Clean and format multiple search results for prompt injection.

        Args:
            results: List of search result dicts with 'title', 'url', 'snippet', and optionally 'content'
            max_chars_total: Override total character limit
            max_chars_per_result: Override per-result character limit

        Returns:
            Formatted string with all cleaned results
        """
        if not results:
            return "No search results available."

        max_chars_total = max_chars_total or self.max_chars
        max_chars_per_result = max_chars_per_result or self.max_chars_per_result

        formatted_results = []
        total_chars = 0

        for i, result in enumerate(results, 1):
            # Stop if we've hit the total limit
            if total_chars >= max_chars_total:
                break

            title = result.get('title', 'Untitled')
            url = result.get('url', '')
            snippet = result.get('snippet', '')
            content = result.get('content', '')

            # Build result block
            result_text = f"### Result {i}: {title}\n"
            result_text += f"URL: {url}\n\n"

            # Add snippet or content
            if content:
                # If we have full HTML content, clean it
                cleaned_content = self.clean_html(
                    content,
                    max_chars=max_chars_per_result - len(result_text)
                )
                result_text += cleaned_content
            elif snippet:
                # Just use the snippet
                result_text += snippet

            # Truncate this result if needed
            remaining_chars = max_chars_total - total_chars
            if len(result_text) > remaining_chars:
                result_text = self._smart_truncate(result_text, remaining_chars)

            formatted_results.append(result_text)
            total_chars += len(result_text)

        return "\n\n---\n\n".join(formatted_results)

    def _remove_ad_elements(self, soup: BeautifulSoup) -> None:
        """Remove elements that likely contain ads or irrelevant content."""
        for element in soup.find_all(True):
            # Check class and id attributes
            classes = element.get('class', [])
            if isinstance(classes, list):
                classes = ' '.join(classes)
            element_id = element.get('id', '')

            combined = f"{classes} {element_id}"

            for pattern in self.AD_PATTERNS:
                if pattern.search(combined):
                    element.decompose()
                    break

    def _find_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        Find the main content area of the page.

        Priority: <main>, <article>, <div role="main">, <body>
        """
        # Try semantic tags first
        for tag in ['main', 'article']:
            element = soup.find(tag)
            if element and len(element.get_text(strip=True)) > 100:
                return element

        # Try role="main"
        element = soup.find(attrs={'role': 'main'})
        if element and len(element.get_text(strip=True)) > 100:
            return element

        # Try common content div classes
        for class_pattern in ['content', 'main', 'article', 'post', 'entry']:
            element = soup.find(class_=re.compile(class_pattern, re.IGNORECASE))
            if element and len(element.get_text(strip=True)) > 100:
                return element

        # Fall back to body
        body = soup.find('body')
        return body if body else soup

    def _clean_markdown(self, markdown: str) -> str:
        """
        Clean up markdown output.

        - Remove excessive whitespace
        - Normalize newlines
        - Remove empty headings
        """
        # Remove excessive whitespace
        markdown = re.sub(r' +', ' ', markdown)

        # Normalize newlines (max 2 consecutive)
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)

        # Remove empty headings
        markdown = re.sub(r'^#+\s*$', '', markdown, flags=re.MULTILINE)

        # Remove lines that are just dashes or equals (leftover from headers)
        markdown = re.sub(r'^[-=]+$', '', markdown, flags=re.MULTILINE)

        # Clean up bullet points (remove empty ones)
        markdown = re.sub(r'^\s*[-*]\s*$', '', markdown, flags=re.MULTILINE)

        # Strip leading/trailing whitespace
        markdown = markdown.strip()

        return markdown

    def _smart_truncate(self, text: str, max_chars: int) -> str:
        """
        Truncate text at a natural boundary (paragraph, sentence, or word).

        Args:
            text: Text to truncate
            max_chars: Maximum characters

        Returns:
            Truncated text with "..." suffix if truncated
        """
        if len(text) <= max_chars:
            return text

        # Leave room for "..."
        max_chars = max_chars - 3

        # Try to cut at paragraph boundary
        truncated = text[:max_chars]
        last_para = truncated.rfind('\n\n')
        if last_para > max_chars * 0.5:  # At least 50% of content
            return truncated[:last_para].strip() + "..."

        # Try to cut at sentence boundary
        last_sentence = max(
            truncated.rfind('. '),
            truncated.rfind('! '),
            truncated.rfind('? ')
        )
        if last_sentence > max_chars * 0.5:
            return truncated[:last_sentence + 1].strip() + "..."

        # Try to cut at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_chars * 0.7:
            return truncated[:last_space].strip() + "..."

        # Just hard truncate
        return truncated.strip() + "..."

    def extract_key_info(self, html: str) -> Dict[str, Any]:
        """
        Extract key information from HTML without full cleaning.

        Useful for quick extraction of metadata.

        Returns:
            Dict with title, description, headings, and key phrases
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Title
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Meta description
            description = ""
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag and desc_tag.get('content'):
                description = desc_tag['content']

            # Main headings
            headings = []
            for h_tag in soup.find_all(['h1', 'h2', 'h3'])[:10]:
                text = h_tag.get_text(strip=True)
                if text and len(text) > 3:
                    headings.append(text)

            return {
                'title': title,
                'description': description,
                'headings': headings,
            }

        except Exception as e:
            print(f"[HTMLCleanerService] Error extracting key info: {e}")
            return {'title': '', 'description': '', 'headings': []}


# Global singleton instance
_html_cleaner: Optional[HTMLCleanerService] = None


def get_html_cleaner(
    max_chars: int = HTMLCleanerService.DEFAULT_MAX_CHARS,
    max_chars_per_result: int = HTMLCleanerService.DEFAULT_MAX_CHARS_PER_RESULT
) -> HTMLCleanerService:
    """
    Get or create the global HTMLCleanerService instance.

    Args:
        max_chars: Maximum total characters (only used on first call)
        max_chars_per_result: Maximum chars per result (only used on first call)

    Returns:
        HTMLCleanerService instance
    """
    global _html_cleaner
    if _html_cleaner is None:
        _html_cleaner = HTMLCleanerService(
            max_chars=max_chars,
            max_chars_per_result=max_chars_per_result
        )
    return _html_cleaner
