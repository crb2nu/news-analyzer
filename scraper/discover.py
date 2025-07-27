"""
Edition discovery module for finding available e-edition content.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from .config import Settings
from .login import verify_session, login
import logging
import re
from datetime import datetime, date
from typing import List, Dict, Optional
from dataclasses import dataclass
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EditionPage:
    """Represents a single page in an e-edition"""
    url: str
    page_number: int
    section: Optional[str] = None
    title: Optional[str] = None
    format: str = "html"  # "html" or "pdf"


@dataclass
class Edition:
    """Represents a complete e-edition for a specific date"""
    date: date
    pages: List[EditionPage]
    base_url: str
    total_pages: int


class EditionDiscoverer:
    """Discovers available e-edition content from swvatoday.com"""
    
    def __init__(self, storage_path: Path = Path("storage_state.json")):
        self.settings = Settings()
        self.storage_path = storage_path
        
    def ensure_authenticated(self) -> bool:
        """Ensure we have a valid authenticated session"""
        if not verify_session(self.storage_path):
            logger.info("Session invalid, attempting login...")
            return login(self.storage_path)
        return True
    
    def discover_today(self) -> Optional[Edition]:
        """Discover today's edition"""
        return self.discover_date(date.today())
    
    def discover_date(self, target_date: date) -> Optional[Edition]:
        """
        Discover e-edition content for a specific date.
        
        Args:
            target_date: The date to discover content for
            
        Returns:
            Edition object if found, None otherwise
        """
        if not self.ensure_authenticated():
            logger.error("Cannot authenticate - discovery failed")
            return None
        
        try:
            with sync_playwright() as p:
                # Get proxy configuration
                proxy_config = self.settings.get_playwright_proxy()
                
                browser = p.chromium.launch(
                    headless=True,
                    proxy=proxy_config
                )
                
                context = browser.new_context(storage_state=str(self.storage_path))
                page = context.new_page()
                
                # Navigate to the e-edition homepage
                base_url = "https://swvatoday.com/eedition/smyth_county/"
                logger.info(f"Navigating to {base_url}")
                page.goto(base_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)
                
                # Check if we need to navigate to a specific date
                edition = self._discover_edition_pages(page, target_date, base_url)
                
                browser.close()
                return edition
                
        except Exception as e:
            logger.error(f"Discovery failed: {str(e)}")
            return None
    
    def _discover_edition_pages(self, page, target_date: date, base_url: str) -> Optional[Edition]:
        """
        Discover all pages in an edition.
        
        This method needs to be adapted based on the actual structure of the e-edition site.
        The implementation below is a template that should be customized after inspecting
        the actual site structure.
        """
        pages = []
        
        try:
            # Method 1: Look for PDF links (common for e-editions)
            pdf_links = page.locator("a[href*='.pdf']").all()
            
            if pdf_links:
                logger.info(f"Found {len(pdf_links)} PDF links")
                for i, link in enumerate(pdf_links):
                    href = link.get_attribute("href")
                    if href:
                        # Make URL absolute if relative
                        if href.startswith("/"):
                            href = f"https://swvatoday.com{href}"
                        elif not href.startswith("http"):
                            href = f"{base_url.rstrip('/')}/{href}"
                        
                        # Extract page info from link text or href
                        link_text = link.text_content() or ""
                        page_num = self._extract_page_number(link_text, href, i + 1)
                        section = self._extract_section(link_text, href)
                        
                        pages.append(EditionPage(
                            url=href,
                            page_number=page_num,
                            section=section,
                            title=link_text.strip() if link_text else None,
                            format="pdf"
                        ))
            
            # Method 2: Look for HTML page navigation (for PageSuite-style e-editions)
            if not pages:
                # Look for page navigation elements
                page_nav = page.locator(".page-nav, .pagination, [class*='page']").first
                if page_nav.is_visible():
                    # Get total pages from navigation
                    nav_text = page_nav.text_content()
                    total_pages = self._extract_total_pages(nav_text)
                    
                    if total_pages:
                        logger.info(f"Found {total_pages} pages in HTML format")
                        for page_num in range(1, total_pages + 1):
                            # Construct URL for each page
                            page_url = f"{base_url}?page={page_num}"
                            pages.append(EditionPage(
                                url=page_url,
                                page_number=page_num,
                                format="html"
                            ))
            
            # Method 3: Look for iframe-based e-edition (some publishers use this)
            if not pages:
                iframe = page.locator("iframe").first
                if iframe.is_visible():
                    iframe_src = iframe.get_attribute("src")
                    if iframe_src:
                        logger.info("Found iframe-based e-edition")
                        # Navigate to iframe content to discover structure
                        iframe_page = page.frame(iframe_src) or page
                        # This would need site-specific implementation
                        pages = self._discover_iframe_pages(iframe_page, base_url)
            
            # If no pages found, create a single entry for the main page
            if not pages:
                logger.warning("No specific pages found, using main page")
                pages.append(EditionPage(
                    url=base_url,
                    page_number=1,
                    format="html"
                ))
            
            edition = Edition(
                date=target_date,
                pages=pages,
                base_url=base_url,
                total_pages=len(pages)
            )
            
            logger.info(f"Discovered {len(pages)} pages for {target_date}")
            return edition
            
        except Exception as e:
            logger.error(f"Page discovery failed: {str(e)}")
            return None
    
    def _extract_page_number(self, text: str, url: str, fallback: int) -> int:
        """Extract page number from text or URL"""
        # Look for patterns like "Page 1", "P1", or numbers in URL
        patterns = [
            r'page\s*(\d+)',
            r'p(\d+)',
            r'(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return int(match.group(1))
            
            match = re.search(pattern, url.lower())
            if match:
                return int(match.group(1))
        
        return fallback
    
    def _extract_section(self, text: str, url: str) -> Optional[str]:
        """Extract section name from text or URL"""
        # Common section names
        sections = [
            "local", "sports", "opinion", "business", "obituaries",
            "classifieds", "entertainment", "news", "editorial"
        ]
        
        text_lower = text.lower()
        url_lower = url.lower()
        
        for section in sections:
            if section in text_lower or section in url_lower:
                return section.title()
        
        return None
    
    def _extract_total_pages(self, nav_text: str) -> Optional[int]:
        """Extract total page count from navigation text"""
        patterns = [
            r'of\s+(\d+)',
            r'/\s*(\d+)',
            r'total:\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, nav_text.lower())
            if match:
                return int(match.group(1))
        
        return None
    
    def _discover_iframe_pages(self, iframe_page, base_url: str) -> List[EditionPage]:
        """Discover pages within an iframe-based e-edition"""
        # This is a placeholder - implementation would depend on the specific
        # iframe content structure used by the publisher
        pages = []
        
        try:
            # Example: Look for navigation within iframe
            nav_elements = iframe_page.locator("[class*='nav'], [class*='page']").all()
            
            for i, element in enumerate(nav_elements):
                href = element.get_attribute("href")
                if href:
                    pages.append(EditionPage(
                        url=href,
                        page_number=i + 1,
                        format="html"
                    ))
        
        except Exception as e:
            logger.error(f"Iframe discovery failed: {str(e)}")
        
        return pages
    
    def save_edition_info(self, edition: Edition, output_path: Path) -> None:
        """Save edition information to JSON file"""
        edition_data = {
            "date": edition.date.isoformat(),
            "base_url": edition.base_url,
            "total_pages": edition.total_pages,
            "pages": [
                {
                    "url": page.url,
                    "page_number": page.page_number,
                    "section": page.section,
                    "title": page.title,
                    "format": page.format
                }
                for page in edition.pages
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(edition_data, f, indent=2)
        
        logger.info(f"Edition info saved to {output_path}")


def main():
    """CLI interface for edition discovery"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Discover e-edition content")
    parser.add_argument("--date", type=str, help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--storage", type=str, default="storage_state.json", help="Session storage file")
    
    args = parser.parse_args()
    
    # Parse date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            exit(1)
    else:
        target_date = date.today()
    
    # Set up output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(f"edition_{target_date.isoformat()}.json")
    
    # Discover edition
    discoverer = EditionDiscoverer(Path(args.storage))
    edition = discoverer.discover_date(target_date)
    
    if edition:
        print(f"Found {edition.total_pages} pages for {target_date}")
        for page in edition.pages:
            print(f"  Page {page.page_number}: {page.url}")
            if page.section:
                print(f"    Section: {page.section}")
        
        discoverer.save_edition_info(edition, output_path)
        print(f"Edition info saved to {output_path}")
    else:
        print(f"No edition found for {target_date}")
        exit(1)


if __name__ == "__main__":
    main()