"""
PDF text extraction module for news analyzer.

This module handles extraction of text content from PDF files with support for:
- Multi-column layout detection
- Page segmentation 
- Article boundary detection
- Metadata preservation
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import re

from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LTTextContainer, LTTextBox, LTTextLine, LTChar
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """Represents a block of text with positioning information."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_number: int
    font_size: Optional[float] = None
    is_title: bool = False
    column: int = 0


@dataclass
class Article:
    """Represents an extracted article with metadata."""
    title: str
    content: str
    page_number: int
    column: int
    x0: float
    y0: float
    x1: float
    y1: float
    word_count: int
    date_published: Optional[datetime] = None
    section: Optional[str] = None
    hash: Optional[str] = None
    
    def __post_init__(self):
        """Calculate content hash after initialization."""
        if not self.hash:
            self.hash = hashlib.md5(
                f"{self.title}{self.content}".encode('utf-8')
            ).hexdigest()


class PDFExtractor:
    """Extract structured text content from PDF files."""
    
    def __init__(self, 
                 column_threshold: float = 50.0,
                 title_font_threshold: float = 1.2,
                 min_article_words: int = 10):
        """
        Initialize PDF extractor.
        
        Args:
            column_threshold: Minimum distance between columns in points
            title_font_threshold: Multiplier for detecting title text (larger fonts)
            min_article_words: Minimum words required for a valid article
        """
        self.column_threshold = column_threshold
        self.title_font_threshold = title_font_threshold
        self.min_article_words = min_article_words
        
        # Configure PDF parsing parameters
        self.laparams = LAParams(
            boxes_flow=0.5,
            word_margin=0.1,
            char_margin=2.0,
            line_margin=0.5,
            detect_vertical=True
        )
    
    def extract_from_file(self, pdf_path: Path) -> List[Article]:
        """
        Extract articles from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of extracted articles
        """
        logger.info(f"Extracting text from PDF: {pdf_path}")
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        try:
            # Extract text blocks with positioning
            text_blocks = self._extract_text_blocks(pdf_path)
            
            # Segment into columns
            columns = self._segment_columns(text_blocks)
            
            # Extract articles from each column
            articles = []
            for column_blocks in columns:
                column_articles = self._extract_articles_from_column(column_blocks)
                articles.extend(column_articles)
            
            logger.info(f"Extracted {len(articles)} articles from {pdf_path}")
            return articles
            
        except Exception as e:
            logger.error(f"Failed to extract from PDF {pdf_path}: {str(e)}")
            raise
    
    def extract_from_bytes(self, pdf_bytes: bytes, filename: str = "unknown.pdf") -> List[Article]:
        """
        Extract articles from PDF bytes.
        
        Args:
            pdf_bytes: PDF content as bytes
            filename: Original filename for logging
            
        Returns:
            List of extracted articles
        """
        # Write to temporary file and extract
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(pdf_bytes)
            tmp_path = Path(tmp_file.name)
        
        try:
            return self.extract_from_file(tmp_path)
        finally:
            # Clean up temporary file
            tmp_path.unlink(missing_ok=True)
    
    def _extract_text_blocks(self, pdf_path: Path) -> List[TextBlock]:
        """Extract text blocks with positioning information."""
        text_blocks = []
        
        with open(pdf_path, 'rb') as file:
            for page_num, page_layout in enumerate(extract_pages(file, laparams=self.laparams), 1):
                for element in page_layout:
                    if isinstance(element, LTTextContainer):
                        text = element.get_text().strip()
                        if text:
                            # Get average font size for the block
                            font_size = self._get_average_font_size(element)
                            
                            text_block = TextBlock(
                                text=text,
                                x0=element.x0,
                                y0=element.y0,
                                x1=element.x1,
                                y1=element.y1,
                                page_number=page_num,
                                font_size=font_size
                            )
                            text_blocks.append(text_block)
        
        return text_blocks
    
    def _get_average_font_size(self, text_container: LTTextContainer) -> Optional[float]:
        """Calculate average font size for a text container."""
        font_sizes = []
        
        def collect_font_sizes(element):
            if isinstance(element, LTChar):
                font_sizes.append(element.height)
            elif hasattr(element, '__iter__'):
                for child in element:
                    collect_font_sizes(child)
        
        collect_font_sizes(text_container)
        
        return sum(font_sizes) / len(font_sizes) if font_sizes else None
    
    def _segment_columns(self, text_blocks: List[TextBlock]) -> List[List[TextBlock]]:
        """Segment text blocks into columns based on X coordinates."""
        if not text_blocks:
            return []
        
        # Group blocks by page first
        pages = {}
        for block in text_blocks:
            if block.page_number not in pages:
                pages[block.page_number] = []
            pages[block.page_number].append(block)
        
        all_columns = []
        
        for page_num, page_blocks in pages.items():
            # Sort blocks by X coordinate
            page_blocks.sort(key=lambda b: b.x0)
            
            # Identify column boundaries
            columns = []
            current_column = []
            last_x = None
            
            for block in page_blocks:
                if last_x is None or abs(block.x0 - last_x) < self.column_threshold:
                    # Same column
                    current_column.append(block)
                    block.column = len(columns)
                else:
                    # New column detected
                    if current_column:
                        columns.append(current_column)
                    current_column = [block]
                    block.column = len(columns)
                
                last_x = block.x0
            
            # Don't forget the last column
            if current_column:
                columns.append(current_column)
            
            # Sort each column by Y coordinate (top to bottom)
            for column in columns:
                column.sort(key=lambda b: -b.y0)  # Negative for top-to-bottom
            
            all_columns.extend(columns)
        
        return all_columns
    
    def _extract_articles_from_column(self, column_blocks: List[TextBlock]) -> List[Article]:
        """Extract individual articles from a column of text blocks."""
        articles = []
        current_article = []
        current_title = None
        
        # Calculate average font size for the column
        font_sizes = [b.font_size for b in column_blocks if b.font_size]
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
        
        for block in column_blocks:
            # Detect if this might be a title (larger font or specific patterns)
            is_title = self._is_likely_title(block, avg_font_size)
            
            if is_title and current_article:
                # Start of new article - save the previous one
                article = self._create_article_from_blocks(current_article, current_title)
                if article:
                    articles.append(article)
                
                # Start new article
                current_article = []
                current_title = block.text.strip()
                block.is_title = True
            elif is_title and not current_article:
                # First title
                current_title = block.text.strip()
                block.is_title = True
            else:
                # Regular content
                current_article.append(block)
        
        # Don't forget the last article
        if current_article:
            article = self._create_article_from_blocks(current_article, current_title)
            if article:
                articles.append(article)
        
        return articles
    
    def _is_likely_title(self, block: TextBlock, avg_font_size: float) -> bool:
        """Determine if a text block is likely a title."""
        # Font size criterion
        if block.font_size and block.font_size > avg_font_size * self.title_font_threshold:
            return True
        
        # Pattern-based detection
        text = block.text.strip()
        
        # All caps and short
        if text.isupper() and len(text.split()) <= 8:
            return True
        
        # Title case and ends without punctuation
        if (text.istitle() and 
            len(text.split()) <= 10 and 
            not text.endswith(('.', '!', '?'))):
            return True
        
        # Starts with typical news patterns
        news_patterns = [
            r'^[A-Z][A-Z\s]{5,}$',  # All caps
            r'^[A-Z][a-z]+ [A-Z][a-z]+',  # Title case
            r'^\w+: ',  # Dateline pattern
        ]
        
        for pattern in news_patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _create_article_from_blocks(self, blocks: List[TextBlock], title: Optional[str]) -> Optional[Article]:
        """Create an article object from text blocks."""
        if not blocks:
            return None
        
        # Combine text content
        content_parts = []
        for block in blocks:
            content_parts.append(block.text.strip())
        
        content = '\n'.join(content_parts).strip()
        
        # Clean up content
        content = re.sub(r'\n\s*\n', '\n\n', content)  # Normalize line breaks
        content = re.sub(r'[ \t]+', ' ', content)  # Normalize spaces
        
        # Check minimum word count
        word_count = len(content.split())
        if word_count < self.min_article_words:
            return None
        
        # Calculate bounding box
        x0 = min(b.x0 for b in blocks)
        y0 = min(b.y0 for b in blocks)
        x1 = max(b.x1 for b in blocks)
        y1 = max(b.y1 for b in blocks)
        
        # Use first block for page/column info
        first_block = blocks[0]
        
        # Clean up title
        if title:
            title = re.sub(r'\s+', ' ', title).strip()
            title = title[:200]  # Truncate very long titles
        else:
            # Generate title from first line of content
            first_line = content.split('\n')[0]
            title = first_line[:100] + ('...' if len(first_line) > 100 else '')
        
        return Article(
            title=title,
            content=content,
            page_number=first_block.page_number,
            column=first_block.column,
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            word_count=word_count
        )


def main():
    """CLI interface for PDF extraction."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Extract articles from PDF files")
    parser.add_argument("pdf_file", help="Path to PDF file")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    parser.add_argument("--min-words", type=int, default=10, 
                       help="Minimum words per article")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Extract articles
    extractor = PDFExtractor(min_article_words=args.min_words)
    articles = extractor.extract_from_file(Path(args.pdf_file))
    
    # Convert to JSON-serializable format
    articles_data = []
    for article in articles:
        articles_data.append({
            'title': article.title,
            'content': article.content,
            'page_number': article.page_number,
            'column': article.column,
            'word_count': article.word_count,
            'hash': article.hash,
            'bounds': {
                'x0': article.x0,
                'y0': article.y0,
                'x1': article.x1,
                'y1': article.y1
            }
        })
    
    # Output results
    output_data = {
        'source_file': str(args.pdf_file),
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