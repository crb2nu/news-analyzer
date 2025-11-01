"""
HTML text extraction module for news analyzer.

This module handles extraction of text content from HTML files with support for:
- Clean text extraction using trafilatura
- Article metadata preservation (title, date, section)
- Dynamic content handling
- Multiple article detection per page
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from urllib.parse import urljoin, urlparse

import trafilatura
from trafilatura.settings import use_config
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class HTMLArticle:
    """Represents an extracted article from HTML with metadata."""
    title: str
    content: str
    url: Optional[str] = None
    date_published: Optional[datetime] = None
    author: Optional[str] = None
    section: Optional[str] = None
    tags: Optional[List[str]] = None
    word_count: int = 0
    hash: Optional[str] = None
    raw_html: Optional[str] = None
    
    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if not self.word_count:
            self.word_count = len(self.content.split())
        
        if not self.hash:
            self.hash = hashlib.md5(
                f"{self.title}{self.content}".encode('utf-8')
            ).hexdigest()


class HTMLExtractor:
    """Extract structured text content from HTML files and web pages."""
    
    def __init__(self, 
                 min_article_words: int = 10,
                 include_raw_html: bool = False,
                 timeout: int = 30):
        """
        Initialize HTML extractor.
        
        Args:
            min_article_words: Minimum words required for a valid article
            include_raw_html: Whether to include raw HTML in results
            timeout: Request timeout in seconds
        """
        self.min_article_words = min_article_words
        self.include_raw_html = include_raw_html
        self.timeout = timeout
        
        # Configure trafilatura
        self.trafilatura_config = use_config()
        self.trafilatura_config.set('DEFAULT', 'MIN_EXTRACTED_SIZE', str(min_article_words * 5))
        self.trafilatura_config.set('DEFAULT', 'MIN_OUTPUT_SIZE', str(min_article_words * 4))
        
        # Setup requests session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def extract_from_url(self, url: str, session_storage: Optional[Dict] = None) -> List[HTMLArticle]:
        """
        Extract articles from a web page URL.
        
        Args:
            url: URL to extract from
            session_storage: Optional session storage for authenticated requests
            
        Returns:
            List of extracted articles
        """
        logger.info(f"Extracting from URL: {url}")
        
        try:
            # Set up headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            # Add session cookies if provided
            if session_storage and 'cookies' in session_storage:
                for cookie in session_storage['cookies']:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))
            
            # Fetch the page
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            return self.extract_from_html(response.text, url)
            
        except Exception as e:
            logger.error(f"Failed to extract from URL {url}: {str(e)}")
            raise
    
    def extract_from_file(self, html_path: Path, base_url: Optional[str] = None) -> List[HTMLArticle]:
        """
        Extract articles from an HTML file.
        
        Args:
            html_path: Path to HTML file
            base_url: Base URL for resolving relative links
            
        Returns:
            List of extracted articles
        """
        logger.info(f"Extracting from HTML file: {html_path}")
        
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            return self.extract_from_html(html_content, base_url or str(html_path))
            
        except Exception as e:
            logger.error(f"Failed to extract from HTML file {html_path}: {str(e)}")
            raise
    
    def extract_from_html(self, html_content: str, source_url: Optional[str] = None) -> List[HTMLArticle]:
        """
        Extract articles from HTML content.
        
        Args:
            html_content: Raw HTML content
            source_url: Source URL for metadata
            
        Returns:
            List of extracted articles
        """
        articles = []
        
        try:
            # First, try to extract the main article using trafilatura
            main_article = self._extract_main_article(html_content, source_url)
            if main_article:
                articles.append(main_article)
            
            # Then, try to find additional articles in the page
            additional_articles = self._extract_additional_articles(html_content, source_url)
            articles.extend(additional_articles)
            
            # Remove duplicates based on content hash
            articles = self._deduplicate_articles(articles)
            
            logger.info(f"Extracted {len(articles)} articles from HTML")
            return articles
            
        except Exception as e:
            logger.error(f"Failed to extract from HTML: {str(e)}")
            raise
    
    def _extract_main_article(self, html_content: str, source_url: Optional[str]) -> Optional[HTMLArticle]:
        """Extract the main article using trafilatura."""
        try:
            # Extract with trafilatura
            extracted = trafilatura.extract(
                html_content,
                output_format='json',
                config=self.trafilatura_config,
                include_comments=False,
                include_tables=True,
                include_images=False,
                url=source_url
            )
            
            if not extracted:
                return None
            
            import json
            data = json.loads(extracted)
            
            # Validate minimum content requirements
            content = data.get('text', '').strip()
            if len(content.split()) < self.min_article_words:
                return None
            
            # Parse date if available
            date_published = None
            if data.get('date'):
                try:
                    date_published = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass
            
            # Extract tags from categories/tags
            tags = []
            if data.get('categories'):
                tags.extend(data['categories'])
            if data.get('tags'):
                tags.extend(data['tags'])
            
            title = self._resolve_title(data.get('title'), content, source_url)

            return HTMLArticle(
                title=title,
                content=content,
                url=source_url,
                date_published=date_published,
                author=data.get('author'),
                section=data.get('sitename') or self._extract_section_from_url(source_url),
                tags=tags if tags else None,
                raw_html=html_content if self.include_raw_html else None
            )
            
        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {str(e)}")
            return None
    
    def _extract_additional_articles(self, html_content: str, source_url: Optional[str]) -> List[HTMLArticle]:
        """Extract additional articles using BeautifulSoup for multi-article pages."""
        articles = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for common article containers
            article_selectors = [
                'article',
                '.article',
                '.post',
                '.news-item',
                '.story',
                '[class*="article"]',
                '[class*="story"]',
                '.content-item'
            ]
            
            found_articles = []
            for selector in article_selectors:
                elements = soup.select(selector)
                found_articles.extend(elements)
            
            # Remove duplicates and nested articles
            unique_articles = self._filter_unique_elements(found_articles)
            
            for element in unique_articles:
                article = self._extract_article_from_element(element, source_url)
                if article:
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.warning(f"Additional article extraction failed: {str(e)}")
            return []
    
    def _filter_unique_elements(self, elements: List) -> List:
        """Filter out nested/duplicate elements."""
        unique_elements = []

        for element in elements:
            # Check if this element is contained within any other element
            is_nested = False
            for other in elements:
                if other != element and element in other.find_all():
                    is_nested = True
                    break
            
            if not is_nested:
                unique_elements.append(element)

        return unique_elements

    def _resolve_title(self, raw_title: Optional[str], content: str, source_url: Optional[str]) -> str:
        title = (raw_title or "").strip()
        if title and not title.lower().startswith("untitled"):
            return title[:200]

        for line in content.split('\n'):
            line = line.strip()
            if len(line.split()) >= 3:
                snippet = line[:200]
                return snippet + ("..." if len(line) > len(snippet) else "")

        if source_url:
            parsed = urlparse(source_url)
            path = parsed.path or source_url
            name = Path(path).name or path
            match = re.search(r"page_(\d+)", name, re.IGNORECASE)
            if match:
                return f"Page {int(match.group(1))}"
            pretty = name.replace('_', ' ').replace('-', ' ').strip()
            if pretty:
                return pretty.title()[:200]

        return "Untitled Article"
    
    def _extract_article_from_element(self, element, source_url: Optional[str]) -> Optional[HTMLArticle]:
        """Extract article data from a BeautifulSoup element."""
        try:
            # Extract title
            raw_title = self._extract_title_from_element(element)
            
            # Extract content text
            content = self._extract_content_from_element(element)
            if not content or len(content.split()) < self.min_article_words:
                return None
            
            title = self._resolve_title(raw_title, content, source_url)
            
            # Extract metadata
            author = self._extract_author_from_element(element)
            date_published = self._extract_date_from_element(element)
            section = self._extract_section_from_element(element) or self._extract_section_from_url(source_url)
            
            return HTMLArticle(
                title=title,
                content=content,
                url=source_url,
                date_published=date_published,
                author=author,
                section=section,
                raw_html=str(element) if self.include_raw_html else None
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract article from element: {str(e)}")
            return None
    
    def _extract_title_from_element(self, element) -> Optional[str]:
        """Extract title from element."""
        title_selectors = [
            'h1', 'h2', 'h3',
            '.title', '.headline', '.article-title',
            '[class*="title"]', '[class*="headline"]'
        ]
        
        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                title = title_elem.get_text().strip()
                if title and len(title) > 5:
                    return title[:200]  # Truncate very long titles
        
        return None
    
    def _extract_content_from_element(self, element) -> Optional[str]:
        """Extract content text from element."""
        # Remove title elements to avoid duplication
        content_element = element.__copy__()
        for title_elem in content_element.find_all(['h1', 'h2', 'h3']):
            title_elem.decompose()
        
        # Extract text content
        content = content_element.get_text().strip()
        
        # Clean up content
        content = re.sub(r'\n\s*\n', '\n\n', content)  # Normalize line breaks
        content = re.sub(r'[ \t]+', ' ', content)  # Normalize spaces
        
        return content if content else None
    
    def _extract_author_from_element(self, element) -> Optional[str]:
        """Extract author from element."""
        author_selectors = [
            '.author', '.byline', '.writer',
            '[class*="author"]', '[class*="byline"]',
            '[rel="author"]'
        ]
        
        for selector in author_selectors:
            author_elem = element.select_one(selector)
            if author_elem:
                author = author_elem.get_text().strip()
                if author:
                    # Clean up common prefixes
                    author = re.sub(r'^(by|author|written by)\s*:?\s*', '', author, flags=re.IGNORECASE)
                    return author[:100]  # Truncate very long author names
        
        return None
    
    def _extract_date_from_element(self, element) -> Optional[datetime]:
        """Extract publication date from element."""
        # Look for datetime attributes
        for datetime_elem in element.find_all(attrs={'datetime': True}):
            try:
                return datetime.fromisoformat(datetime_elem['datetime'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                continue
        
        # Look for date text patterns
        date_selectors = [
            '.date', '.published', '.timestamp',
            '[class*="date"]', '[class*="time"]'
        ]
        
        for selector in date_selectors:
            date_elem = element.select_one(selector)
            if date_elem:
                date_text = date_elem.get_text().strip()
                parsed_date = self._parse_date_text(date_text)
                if parsed_date:
                    return parsed_date
        
        return None
    
    def _extract_section_from_element(self, element) -> Optional[str]:
        """Extract section/category from element."""
        section_selectors = [
            '.section', '.category', '.topic',
            '[class*="section"]', '[class*="category"]'
        ]
        
        for selector in section_selectors:
            section_elem = element.select_one(selector)
            if section_elem:
                section = section_elem.get_text().strip()
                if section:
                    return section[:50]  # Truncate long section names
        
        return None
    
    def _extract_section_from_url(self, url: Optional[str]) -> Optional[str]:
        """Extract section from URL path."""
        if not url:
            return None
        
        try:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]
            
            # Common section indicators in URL paths
            if len(path_parts) >= 2:
                return path_parts[0].replace('-', ' ').title()
        except:
            pass
        
        return None
    
    def _parse_date_text(self, date_text: str) -> Optional[datetime]:
        """Parse date from text using common patterns."""
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
            r'(\w+ \d{1,2}, \d{4})',  # Month DD, YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    date_str = match.group(1)
                    if '/' in date_str:
                        return datetime.strptime(date_str, '%m/%d/%Y')
                    elif '-' in date_str:
                        return datetime.strptime(date_str, '%Y-%m-%d')
                    else:
                        return datetime.strptime(date_str, '%B %d, %Y')
                except ValueError:
                    continue
        
        return None
    
    def _deduplicate_articles(self, articles: List[HTMLArticle]) -> List[HTMLArticle]:
        """Remove duplicate articles based on content hash."""
        seen_hashes = set()
        unique_articles = []
        
        for article in articles:
            if article.hash not in seen_hashes:
                seen_hashes.add(article.hash)
                unique_articles.append(article)
        
        return unique_articles


def main():
    """CLI interface for HTML extraction."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Extract articles from HTML files or URLs")
    parser.add_argument("source", help="HTML file path or URL")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    parser.add_argument("--min-words", type=int, default=10, 
                       help="Minimum words per article")
    parser.add_argument("--include-html", action="store_true",
                       help="Include raw HTML in output")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Extract articles
    extractor = HTMLExtractor(
        min_article_words=args.min_words,
        include_raw_html=args.include_html
    )
    
    if args.source.startswith(('http://', 'https://')):
        articles = extractor.extract_from_url(args.source)
    else:
        articles = extractor.extract_from_file(Path(args.source))
    
    # Convert to JSON-serializable format
    articles_data = []
    for article in articles:
        article_dict = {
            'title': article.title,
            'content': article.content,
            'url': article.url,
            'word_count': article.word_count,
            'hash': article.hash,
            'author': article.author,
            'section': article.section,
            'tags': article.tags
        }
        
        if article.date_published:
            article_dict['date_published'] = article.date_published.isoformat()
        
        if article.raw_html:
            article_dict['raw_html'] = article.raw_html
        
        articles_data.append(article_dict)
    
    # Output results
    output_data = {
        'source': args.source,
        'extraction_time': datetime.utcnow().isoformat(),
        'article_count': len(articles),
        'articles': articles_data
    }
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Extracted {len(articles)} articles to {args.output}")
    else:
        print(json.dumps(output_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
