"""
Edition discovery module for finding available e-edition content.
"""

from pathlib import Path
from contextlib import suppress
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    BrowserContext,
    Page,
)
from .config import Settings
from .login import verify_session, login
import logging
import re
from datetime import datetime, date
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
import json
from urllib.parse import urljoin, urlparse
from .normalize import normalize_section

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PUBLICATION = "Smyth County News & Messenger"
PUBLICATION_SLUGS = {
    "Smyth County News & Messenger": "smyth_county",
    "The News & Press": "richlands",
    "The Bland County Messenger": "bland_county",
    "The Floyd Press": "floyd",
    "Wytheville Enterprise": "wytheville",
    "Washington County News": "washington_county",
}
PUBLICATION_SLUG_TO_DISPLAY = {slug: name for name, slug in PUBLICATION_SLUGS.items()}
PUBLICATION_TABS = list(PUBLICATION_SLUGS.keys())


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
    publication: str = DEFAULT_PUBLICATION


class EditionDiscoverer:
    """Discovers available e-edition content from swvatoday.com"""
    
    def __init__(self, storage_path: Path = Path("storage_state.json")):
        self.settings = Settings()
        self.storage_path = storage_path
        self._pw = None
        self._browser = None
        self._authed = False
        
    def ensure_authenticated(self) -> bool:
        """Ensure we have a valid authenticated session (single login per process).

        We attempt a real verification once; after a successful login we reuse the
        stored state for subsequent publications to avoid repeated logins.
        """
        if self._authed:
            return True
        if verify_session(self.storage_path):
            self._authed = True
            return True
        logger.info("Session invalid, attempting login...")
        ok = login(self.storage_path)
        self._authed = bool(ok)
        return ok
    
    def get_available_publications(self) -> List[str]:
        return PUBLICATION_TABS.copy()

    def discover_today(self, publication: Optional[str] = None) -> Optional[Edition]:
        """Discover today's edition"""
        return self.discover_date(date.today(), publication)

    def discover_date(self, target_date: date, publication: Optional[str] = None) -> Optional[Edition]:
        """
        Discover e-edition content for a specific date.
        
        Args:
            target_date: The date to discover content for
            publication: Optional publication/tab name to target
            
        Returns:
            Edition object if found, None otherwise
        """
        if not self.ensure_authenticated():
            logger.error("Cannot authenticate - discovery failed")
            return None
        
        publication = publication or DEFAULT_PUBLICATION
        selected_publication = publication
        try:
            # Launch/reuse a single browser per process to save memory
            if self._pw is None or self._browser is None:
                self._pw = sync_playwright().start()
                proxy_config = self.settings.get_playwright_proxy()
                self._browser = self._pw.firefox.launch(
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

            context = self._browser.new_context(storage_state=str(self.storage_path))
            # Reduce bandwidth and memory: block heavy resources
            try:
                def _route_handler(route, request):
                    rtype = request.resource_type
                    url = request.url
                    if rtype in ("image", "media", "font"):
                        return route.abort()
                    # Skip common analytics/ads
                    if any(s in url for s in ("googletagmanager", "doubleclick", "adservice", "analytics", "facebook")):
                        return route.abort()
                    return route.continue_()
                context.route("**/*", _route_handler)
            except Exception:
                pass
                page = context.new_page()
                
                # Navigate to the e-edition root (allows switching across publications)
                base_url = "https://swvatoday.com/eedition/"
                logger.info(f"Navigating to {base_url}")
                page.goto(base_url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                self._dismiss_cookie_banner(page)
                if not self._select_publication(page, publication):
                    logger.info("Could not select publication %s; staying on default", publication)
                    selected_publication = DEFAULT_PUBLICATION
                else:
                    selected_publication = publication
                    base_url = self._derive_base_url(page.url)

                index_url = self._find_edition_in_index(page, target_date, base_url)
                replacement_page: Optional[Union[str, Page]] = None
                if index_url:
                    page.goto(index_url, timeout=60000, wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle", timeout=15000)
                    base_url = self._derive_base_url(page.url)
                else:
                    replacement_page = self._open_edition_from_search(context, page, target_date, base_url)
                if isinstance(replacement_page, Page):
                    page = replacement_page
                    base_url = self._derive_base_url(page.url)
                elif isinstance(replacement_page, str):
                    page.goto(replacement_page, timeout=60000, wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle", timeout=15000)
                    base_url = self._derive_base_url(page.url)
                else:
                    # Fall back to in-viewer date navigation if search fails
                    if not self._navigate_to_date(page, target_date):
                        logger.warning(f"Could not navigate directly to {target_date}; attempting current edition")
                        base_url = self._derive_base_url(page.url)
                current_publication = selected_publication or self._infer_publication_from_url(page.url)
                if current_publication:
                    selected_publication = current_publication

                # Wait briefly for viewer content to settle
                page.wait_for_timeout(2000)

                edition = self._discover_edition_pages(page, target_date, base_url)
                
                if edition:
                    edition.publication = selected_publication
                return edition
                
        except Exception as e:
            logger.error(f"Discovery failed: {str(e)}")
            return None

    def close(self):
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
    
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
    
    def _open_edition_from_search(
        self,
        context: BrowserContext,
        page: Page,
        target_date: date,
        base_url: str,
    ) -> Optional[Union[str, Page]]:
        """Attempt to load the requested edition via the e-edition search widget."""
        try:
            self._ensure_search_panel_visible(page)

            date_value = target_date.strftime("%m/%d/%Y")
            self._fill_input_candidates(
                page,
                [
                    "input[placeholder*='from' i]",
                    "input[name*='from']",
                    "input[id*='from']",
                ],
                date_value,
            )
            self._fill_input_candidates(
                page,
                [
                    "input[placeholder*='to' i]",
                    "input[name*='to']",
                    "input[id*='to']",
                ],
                date_value,
            )

            self._set_results_per_page(page)

            search_buttons = page.locator("form button:has-text('Search')")
            if search_buttons.count() == 0:
                search_buttons = page.locator("button:has-text('Search')")

            if search_buttons.count() == 0:
                return None

            with suppress(Exception):
                search_buttons.last.click()
                page.wait_for_load_state("networkidle", timeout=20000)
                page.wait_for_timeout(1500)

            link_locator = self._find_result_link(page, target_date)
            if not link_locator:
                return None

            href = link_locator.get_attribute("href")
            if href:
                return self._normalize_url(base_url, href)

            with context.expect_page() as popup_event:
                link_locator.click()
            new_page = popup_event.value
            new_page.wait_for_load_state("networkidle", timeout=20000)
            return new_page

        except Exception as exc:
            logger.error(f"Edition search failed: {exc}")
            return None

    def _find_edition_in_index(self, page: Page, target_date: date, base_url: str) -> Optional[str]:
        """Scan the edition index cards for the exact target date and return its URL."""
        try:
            cards = page.locator("article.tnt-asset-type-edition")
            count = min(cards.count(), 40)
            if count == 0:
                return None

            for idx in range(count):
                card = cards.nth(idx)
                time_el = card.locator("time[datetime]").first
                edition_date = None
                if time_el.count():
                    dt_attr = time_el.get_attribute("datetime")
                    edition_date = self._parse_date_value(dt_attr)
                    if not edition_date:
                        try:
                            edition_date = self._parse_date_value(time_el.inner_text())
                        except Exception:
                            edition_date = None
                else:
                    try:
                        text = card.inner_text()
                        edition_date = self._parse_date_value(text)
                    except Exception:
                        edition_date = None

                if edition_date != target_date:
                    continue

                link = card.locator("a.tnt-asset-link").first
                if link.count():
                    href = link.get_attribute("href")
                    normalized = self._normalize_url(base_url, href)
                    if normalized:
                        logger.info("Found edition for %s on %s via index", target_date, normalized)
                        return normalized

            return None
        except Exception as exc:
            logger.debug("Edition index scan failed: %s", exc)
            return None

    def _navigate_to_date(self, page, target_date: date) -> bool:
        """
        Navigate to a specific date in the PageSuite e-edition.
        
        Returns True if navigation was successful, False otherwise.
        """
        try:
            # Method 1: Look for a date picker or calendar
            date_picker = page.locator(
                "input[type='date'], input[name*='date' i], input[id*='date' i]"
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
                    page.wait_for_load_state("networkidle", timeout=45000)
                    return True
            
            # Method 2: Look for date navigation links
            date_links = page.locator(f"a:has-text('{target_date.strftime('%B %d, %Y')}')").all()
            if date_links:
                date_links[0].click()
                page.wait_for_load_state("networkidle", timeout=45000)
                return True
            
            # Method 3: URL-based navigation
            # Many PageSuite sites use date in URL
            date_url = f"{page.url}?date={target_date.strftime('%Y-%m-%d')}"
            page.goto(date_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=45000)
            
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

    def _dismiss_cookie_banner(self, page: Page) -> None:
        selectors = [
            "button:has-text('Accept')",
            "button:has-text('I Agree')",
            "button[aria-label*='Accept']",
        ]
        for selector in selectors:
            with suppress(Exception):
                button = page.locator(selector).first
                if button.count():
                    button.click()
                    page.wait_for_timeout(500)
                    break

    def _select_publication(self, page: Page, publication_name: str) -> bool:
        normalized_name = (publication_name or "").strip()
        slug = PUBLICATION_SLUGS.get(normalized_name)
        if not slug:
            for display_name, candidate_slug in PUBLICATION_SLUGS.items():
                if display_name.lower() == normalized_name.lower():
                    slug = candidate_slug
                    break

        if slug:
            target_url = urljoin("https://swvatoday.com", f"/eedition/{slug}/")
            try:
                logger.debug("Attempting direct navigation for publication '%s' via slug '%s'", publication_name, slug)
                if not page.url.startswith(target_url):
                    page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle", timeout=15000)
                    page.wait_for_timeout(1000)
                logger.info("Switched to publication '%s' via direct navigation (%s)", publication_name, target_url)
                return True
            except Exception as exc:  # fall back to interactive selectors
                logger.debug("Direct navigation to %s failed: %s", target_url, exc)
        else:
            logger.debug("No slug mapping found for publication '%s'", publication_name)

        # Fallback: attempt to click visible tab/link
        selectors = [
            f"a:has-text('{publication_name}')",
            f"button:has-text('{publication_name}')",
            f"[role='tab']:has-text('{publication_name}')",
            f"[data-publication-name*='{publication_name}']",
            "ul.list-inline li a[href*='/eedition']",
        ]
        for selector in selectors:
            with suppress(Exception):
                tab = page.locator(selector).first
                if tab.count():
                    tab.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
                    page.wait_for_timeout(500)
                    logger.info("Switched to publication '%s' via interactive selector '%s'", publication_name, selector)
                    return True
        return False

    def _ensure_search_panel_visible(self, page: Page) -> None:
        with suppress(Exception):
            toggle = page.locator("button:has-text('Search e-Editions')").first
            if toggle.count():
                toggle.click()
                page.wait_for_timeout(300)

    def _fill_input_candidates(self, page: Page, selectors: List[str], value: str) -> bool:
        for selector in selectors:
            with suppress(Exception):
                locator = page.locator(selector).first
                if locator.count():
                    locator.click()
                    locator.fill(value)
                    return True
        return False

    def _set_results_per_page(self, page: Page) -> None:
        select_candidates = [
            "select[name*='results']",
            "select[id*='results']",
            "select[aria-label*='Results']",
            "select",
        ]
        options_to_try = ["20", "25", "30", "50", "100"]
        for selector in select_candidates:
            with suppress(Exception):
                select_input = page.locator(selector).first
                if not select_input.count():
                    continue
                for option in options_to_try:
                    with suppress(Exception):
                        select_input.select_option(value=option)
                        return
                    with suppress(Exception):
                        select_input.select_option(label=option)
                        return
                with suppress(Exception):
                    opt_locator = select_input.locator("option")
                    count = opt_locator.count()
                    if count:
                        last_value = opt_locator.nth(count - 1).get_attribute("value")
                        if last_value:
                            select_input.select_option(value=last_value)
                return

    def _find_result_link(self, page: Page, target_date: date):
        variants = self._format_date_variants(target_date)

        for variant in variants:
            locator = page.locator(f"a:has-text('{variant}')").first
            if locator.count():
                return locator

        date_attr = target_date.strftime("%Y-%m-%d")
        locator = page.locator(f"[data-date='{date_attr}'] a").first
        if locator.count():
            return locator

        link_candidates = page.locator("a[href*='/eedition']")
        total_links = min(link_candidates.count(), 40)
        for idx in range(total_links):
            candidate = link_candidates.nth(idx)
            with suppress(Exception):
                text = (candidate.inner_text() or "").strip()
            if any(variant.lower() in text.lower() for variant in variants):
                return candidate

        cards = page.locator("[data-date], .search-result, .result-card, article")
        total_cards = min(cards.count(), 40)
        for idx in range(total_cards):
            card = cards.nth(idx)
            with suppress(Exception):
                text = (card.inner_text() or "").strip()
            if any(variant.lower() in text.lower() for variant in variants):
                link = card.locator("a").first
                if link.count():
                    return link
        return None

    def _format_date_variants(self, target_date: date) -> List[str]:
        formats = [
            "%B %-d, %Y",
            "%B %#d, %Y",
            "%b %-d, %Y",
            "%b %#d, %Y",
            "%A, %B %-d, %Y",
            "%A, %B %#d, %Y",
            "%m/%d/%Y",
            "%#m/%#d/%Y",
            "%Y-%m-%d",
        ]
        variants = set()
        for fmt in formats:
            with suppress(ValueError):
                variants.add(target_date.strftime(fmt))
        variants.discard("")
        return list(variants)

    def _derive_base_url(self, url: str) -> str:
        if not url:
            return "https://swvatoday.com/eedition/"
        parsed = urlparse(url)
        path = parsed.path
        if not path.endswith('/'):
            path = path.rsplit('/', 1)[0] + '/'
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _infer_publication_from_url(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
        except Exception:
            return None
        parts = [part for part in parsed.path.split('/') if part]
        for part in reversed(parts):
            slug = part.lower()
            slug_alt = slug.replace('-', '_')
            if slug in PUBLICATION_SLUG_TO_DISPLAY:
                return PUBLICATION_SLUG_TO_DISPLAY[slug]
            if slug_alt in PUBLICATION_SLUG_TO_DISPLAY:
                return PUBLICATION_SLUG_TO_DISPLAY[slug_alt]
        return None

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

    def _parse_date_value(self, value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        text = value.strip()
        if not text:
            return None
        cleaned = text.replace("Z", "")
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.date()
            except ValueError:
                continue
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                dt = datetime.strptime(text, fmt)
                return dt.date()
            except ValueError:
                continue
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
        """Extract and normalize a section name from text or URL."""
        candidates = [
            "local", "sports", "opinion", "business", "obituaries",
            "classifieds", "entertainment", "news", "editorial",
            "police", "police and courts", "crime",
        ]

        text_lower = text.lower()
        url_lower = url.lower()

        for raw in candidates:
            if raw in text_lower or raw in url_lower:
                return normalize_section(raw)

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
