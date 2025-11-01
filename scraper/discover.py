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
from urllib.parse import urljoin

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
                
                # Prefer Firefox in containers for stability
                browser = p.firefox.launch(
                    headless=True,
                    proxy=proxy_config,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--single-process",
                        "--no-zygote",
                    ],
                )
                
                context = browser.new_context(storage_state=str(self.storage_path))
                page = context.new_page()
                
                # Navigate to the e-edition homepage
                base_url = "https://swvatoday.com/eedition/smyth_county/"
                logger.info(f"Navigating to {base_url}")
                page.goto(base_url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                
                # Check if we need to navigate to a specific date
                edition = self._discover_edition_pages(page, target_date, base_url)
                
                browser.close()
                return edition
                
        except Exception as e:
            logger.error(f"Discovery failed: {str(e)}")
            return None
    
    def _discover_edition_pages(self, page, target_date: date, base_url: str) -> Optional[Edition]:
        """
        Discover all pages in a PageSuite e-edition.
        
        PageSuite typically provides:
        1. A date selector/calendar for choosing editions
        2. PDF downloads for each page
        3. An HTML viewer with page thumbnails
        4. Navigation controls for moving between pages
        """
        pages: List[EditionPage] = []
        
        try:
            # First, navigate to the specific date if not today
            if target_date != date.today():
                if not self._navigate_to_date(page, target_date):
                    logger.warning(f"Could not navigate to date {target_date}, using current edition")
            
            # Wait for the edition to load
            page.wait_for_timeout(2000)

            # Method 0: Parse the index list of "Page A1" style links
            pages = self._collect_index_page_links(page, base_url)
            if pages:
                logger.info(f"Found {len(pages)} page links from edition index")
            
            # Method 1: Look for PageSuite PDF download links
            # PageSuite often uses a pattern like "Download PDF" or icons with PDF links
            pdf_links = [] if pages else page.locator(
                "a[href*='.pdf'], a[download*='.pdf'], a[title*='PDF'], a[aria-label*='PDF']"
            ).all()
            
            if pdf_links:
                logger.info(f"Found {len(pdf_links)} PDF links")
                for i, link in enumerate(pdf_links):
                    href = link.get_attribute("href")
                    if href and '.pdf' in href.lower():
                        # Make URL absolute if relative
                        if href.startswith("/"):
                            href = f"https://swvatoday.com{href}"
                        elif not href.startswith("http"):
                            href = f"{base_url.rstrip('/')}/{href}"
                        
                        # Extract page info from link text, title, or aria-label
                        link_text = link.text_content() or ""
                        link_title = link.get_attribute("title") or ""
                        link_aria = link.get_attribute("aria-label") or ""
                        
                        # Combine all text sources for better extraction
                        combined_text = f"{link_text} {link_title} {link_aria}"
                        
                        page_num = self._extract_page_number(combined_text, href, i + 1)
                        section = self._extract_section(combined_text, href)
                        
                        pages.append(EditionPage(
                            url=href,
                            page_number=page_num,
                            section=section,
                            title=link_text.strip() if link_text else None,
                            format="pdf"
                        ))
            
            # Method 2: Look for PageSuite viewer with page thumbnails
            if not pages:
                # PageSuite often uses thumbnail grids or lists for page navigation
                thumbnails = page.locator(
                    "img[class*='thumb'], img[class*='page'], "
                    "div[class*='thumb'] img, div[class*='page-thumb'] img, "
                    ".page-thumbnail img, .edition-page img"
                ).all()
                
                if thumbnails:
                    logger.info(f"Found {len(thumbnails)} page thumbnails")
                    for i, thumb in enumerate(thumbnails):
                        # Get the parent link or the thumbnail's data attributes
                        parent = thumb.locator("xpath=ancestor::a").first
                        
                        if parent.count() > 0:
                            href = parent.get_attribute("href")
                        else:
                            # Try to find associated PDF link
                            page_id = thumb.get_attribute("data-page") or thumb.get_attribute("data-page-id")
                            if page_id:
                                # Construct PDF URL based on common PageSuite patterns
                                href = f"{base_url}download/page_{page_id}.pdf"
                            else:
                                # Use thumbnail source as fallback
                                thumb_src = thumb.get_attribute("src")
                                if thumb_src:
                                    # Convert thumbnail URL to PDF URL (common pattern)
                                    href = thumb_src.replace("/thumb/", "/pdf/").replace(".jpg", ".pdf").replace(".png", ".pdf")
                                else:
                                    continue
                        
                        if href:
                            # Make URL absolute
                            if href.startswith("/"):
                                href = f"https://swvatoday.com{href}"
                            elif not href.startswith("http"):
                                href = f"{base_url.rstrip('/')}/{href}"
                            
                            # Extract alt text or title for metadata
                            alt_text = thumb.get_attribute("alt") or ""
                            title_text = thumb.get_attribute("title") or ""
                            
                            page_num = self._extract_page_number(f"{alt_text} {title_text}", href, i + 1)
                            section = self._extract_section(f"{alt_text} {title_text}", href)
                            
                            pages.append(EditionPage(
                                url=href,
                                page_number=page_num,
                                section=section,
                                title=alt_text or title_text or None,
                                format="pdf" if ".pdf" in href else "html"
                            ))
            
            # Method 3: Look for PageSuite viewer iframe
            if not pages:
                # PageSuite sometimes embeds the viewer in an iframe
                iframe = page.locator("iframe[src*='pagesuite'], iframe[src*='edition'], iframe[id*='viewer']").first
                if iframe.count() > 0:
                    iframe_src = iframe.get_attribute("src")
                    if iframe_src:
                        logger.info(f"Found PageSuite viewer iframe: {iframe_src}")
                        
                        # Make iframe URL absolute
                        if iframe_src.startswith("/"):
                            iframe_src = f"https://swvatoday.com{iframe_src}"
                        elif not iframe_src.startswith("http"):
                            iframe_src = f"{base_url.rstrip('/')}/{iframe_src}"
                        
                        # Navigate to iframe content directly
                        page.goto(iframe_src)
                        page.wait_for_load_state("networkidle", timeout=10000)
                        
                        # Now try to discover pages in the iframe content
                        pages = self._discover_pagesuite_viewer_pages(page, base_url)
            
            # Method 4: Look for page navigation controls
            if not pages:
                # Check for page count in navigation
                page_count_elem = page.locator(
                    "[class*='page-count'], [class*='total-pages'], "
                    "[data-total-pages], .navigation-info"
                ).first
                
                if page_count_elem.count() > 0:
                    count_text = page_count_elem.text_content()
                    total_pages = self._extract_total_pages(count_text)
                    
                    if total_pages:
                        logger.info(f"Found {total_pages} pages from navigation")
                        
                        # Generate page URLs based on pattern
                        for page_num in range(1, total_pages + 1):
                            # Common PageSuite URL patterns
                            page_url = f"{base_url}page/{page_num}"
                            
                            # Try to determine if PDF is available
                            pdf_url = f"{base_url}download/page_{page_num}.pdf"
                            
                            pages.append(EditionPage(
                                url=pdf_url,  # Prefer PDF if available
                                page_number=page_num,
                                format="pdf"
                            ))
            
            # Fallback: Create at least one page entry
            if not pages:
                logger.warning("No specific pages found, attempting to extract from current view")
                
                # Check if we're already viewing a page
                current_page_elem = page.locator("[class*='current-page'], [class*='active'][class*='page']").first
                if current_page_elem.count() > 0:
                    pages.append(EditionPage(
                        url=page.url,
                        page_number=1,
                        format="html"
                    ))
                else:
                    # Use the base URL as fallback
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

    def _collect_index_page_links(self, page, base_url: str) -> List[EditionPage]:
        """Collect page links from the landing index (e.g., "Page A1")"""
        try:
            anchors = page.locator("a").all()
        except Exception:
            return []

        pages: List[EditionPage] = []
        seen_urls: set[str] = set()

        for anchor in anchors:
            try:
                text = (anchor.text_content() or "").strip()
            except Exception:
                continue

            if not text or not re.search(r"\bpage\s+[a-z]?\d+\b", text, flags=re.IGNORECASE):
                continue

            href = anchor.get_attribute("data-download") or anchor.get_attribute("href")
            href = self._normalize_url(base_url, href)
            if not href or href in seen_urls:
                continue

            page_num = self._extract_page_number(text, href, len(pages) + 1)
            section = self._extract_section(text, href)

            format_type = "pdf" if href.lower().endswith(".pdf") else "html"

            pages.append(EditionPage(
                url=href,
                page_number=page_num,
                section=section,
                title=text,
                format=format_type,
            ))
            seen_urls.add(href)

        pages.sort(key=lambda p: (p.page_number, p.section or ""))
        return pages
    
    def _navigate_to_date(self, page, target_date: date) -> bool:
        """
        Navigate to a specific date in the PageSuite e-edition.
        
        Returns True if navigation was successful, False otherwise.
        """
        try:
            # Method 1: Look for a date picker or calendar
            date_picker = page.locator(
                "input[type='date'], input[class*='date'], "
                "[class*='calendar'], [class*='datepicker']"
            ).first
            
            if date_picker.count() > 0:
                # Format date for input
                date_str = target_date.strftime("%Y-%m-%d")
                date_picker.fill(date_str)
                
                # Look for a submit/go button
                go_button = page.locator(
                    "button[type='submit'], button:has-text('Go'), "
                    "button:has-text('View'), button:has-text('Load')"
                ).first
                
                if go_button.count() > 0:
                    go_button.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    return True
            
            # Method 2: Look for date navigation links
            date_links = page.locator(f"a:has-text('{target_date.strftime('%B %d, %Y')}')").all()
            if date_links:
                date_links[0].click()
                page.wait_for_load_state("networkidle", timeout=10000)
                return True
            
            # Method 3: URL-based navigation
            # Many PageSuite sites use date in URL
            date_url = f"{page.url}?date={target_date.strftime('%Y-%m-%d')}"
            page.goto(date_url)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Check if the date navigation worked
            # Look for date display on page
            date_display = page.locator(f"*:has-text('{target_date.strftime('%B %d, %Y')}')").first
            if date_display.count() > 0:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Date navigation failed: {str(e)}")
            return False
    
    def _discover_pagesuite_viewer_pages(self, page, base_url: str) -> List[EditionPage]:
        """
        Discover pages within a PageSuite viewer interface.
        
        This handles the specific PageSuite viewer that might be loaded
        in an iframe or as the main content.
        """
        pages = []
        
        try:
            # PageSuite viewer specific selectors
            # Look for page list or grid
            page_items = page.locator(
                ".page-item, .page-tile, .edition-page-item, "
                "[data-page-number], [data-page-id]"
            ).all()
            
            if page_items:
                logger.info(f"Found {len(page_items)} pages in PageSuite viewer")
                
                for item in page_items:
                    # Extract page number
                    page_num_attr = item.get_attribute("data-page-number") or item.get_attribute("data-page")
                    if not page_num_attr:
                        # Try to extract from text
                        item_text = item.text_content() or ""
                        page_num_match = re.search(r'\d+', item_text)
                        page_num = int(page_num_match.group()) if page_num_match else len(pages) + 1
                    else:
                        page_num = int(page_num_attr)
                    
                    # Look for download link
                    download_link = item.locator("a[download], a[href*='.pdf']").first
                    if download_link.count() > 0:
                        href = download_link.get_attribute("href")
                    else:
                        # Construct PDF URL based on page number
                        href = f"{base_url}download/page_{page_num}.pdf"
                    
                    if href:
                        # Make URL absolute
                        if href.startswith("/"):
                            href = f"https://swvatoday.com{href}"
                        elif not href.startswith("http"):
                            href = f"{base_url.rstrip('/')}/{href}"
                        
                        pages.append(EditionPage(
                            url=href,
                            page_number=page_num,
                            format="pdf" if ".pdf" in href else "html"
                        ))
            
            # Alternative: Look for viewer controls
            if not pages:
                # Check for total pages in viewer info
                viewer_info = page.locator(
                    ".viewer-info, .page-info, [class*='page-counter']"
                ).first
                
                if viewer_info.count() > 0:
                    info_text = viewer_info.text_content()
                    total_pages = self._extract_total_pages(info_text)
                    
                    if total_pages:
                        logger.info(f"Found {total_pages} pages from viewer info")
                        
                        for page_num in range(1, total_pages + 1):
                            # Generate URLs based on PageSuite patterns
                            pdf_url = f"{base_url}edition/page_{page_num}.pdf"
                            
                            pages.append(EditionPage(
                                url=pdf_url,
                                page_number=page_num,
                                format="pdf"
                            ))
        
        except Exception as e:
            logger.error(f"PageSuite viewer discovery failed: {str(e)}")
        
        return pages

    def _normalize_url(self, base_url: str, href: Optional[str]) -> Optional[str]:
        """Convert relative or protocol-relative URLs to absolute ones"""
        if not href:
            return None

        href = href.strip()
        if not href or href.startswith("javascript:") or href in ("#", ""):
            return None

        if href.startswith("//"):
            return f"https:{href}"

        if href.startswith("http://") or href.startswith("https://"):
            return href

        if href.startswith("/"):
            return f"https://swvatoday.com{href}"

        return urljoin(base_url, href)
    
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
            r'(\d+)\s*pages?',
            r'page\s*\d+\s*of\s*(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, nav_text.lower())
            if match:
                return int(match.group(1))
        
        # Also try to find just a number if it's the only/largest number
        numbers = re.findall(r'\d+', nav_text)
        if numbers:
            # Return the largest number as it's likely the total
            return max(int(n) for n in numbers)
        
        return None
    
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
