"""
Download and caching system with MinIO support for Kubernetes deployment.
"""

import os
import re
import hashlib
import logging
from pathlib import Path
from datetime import date, datetime
from typing import List, Optional, Dict, Any
import requests
from urllib.parse import urlparse
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# MinIO client
from minio import Minio
from minio.error import S3Error

# Local imports
from .config import Settings
from .discover import Edition, EditionPage, PUBLICATION_TABS, DEFAULT_PUBLICATION

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DownloadCache:
    """Handles downloading and caching of e-edition content using MinIO"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.minio_client = None
        self._init_minio()
    
    def _init_minio(self):
        """Initialize MinIO client with sensible in-cluster defaults.

        - Treat Kubernetes service DNS (".svc"/".svc.cluster.local") as HTTP (secure=False)
          and default to port 80 if none provided.
        - For localhost/.lan also use HTTP.
        - Otherwise default to HTTPS on port 9000 when port is omitted.
        """
        try:
            ep = self.settings.minio_endpoint.strip()
            # Strip scheme if given
            if ep.startswith("http://"):
                ep = ep[len("http://"):]
                default_secure = False
            elif ep.startswith("https://"):
                ep = ep[len("https://"):]
                default_secure = True
            else:
                default_secure = None  # decide below

            # Split host:port
            if ":" in ep:
                host, port_str = ep.rsplit(":", 1)
                try:
                    port = int(port_str)
                except ValueError:
                    host, port = ep, None
            else:
                host, port = ep, None

            # Heuristics for secure + default port
            is_k8s_svc = host.endswith(".svc") or host.endswith(".svc.cluster.local")
            is_local = host.startswith("localhost") or host.endswith(".lan")

            if default_secure is None:
                secure = not (is_k8s_svc or is_local)
            else:
                secure = default_secure

            if port is None:
                port = 80 if not secure else 9000

            endpoint = f"{host}:{port}"

            self.minio_client = Minio(
                endpoint,
                access_key=self.settings.minio_access_key,
                secret_key=self.settings.minio_secret_key,
                secure=secure,
            )

            # Create bucket if it doesn't exist
            if not self.minio_client.bucket_exists(self.settings.minio_bucket):
                self.minio_client.make_bucket(self.settings.minio_bucket)
                logger.info(f"Created bucket: {self.settings.minio_bucket}")

            logger.info(
                "MinIO client initialized (endpoint=%s secure=%s)", endpoint, secure
            )

        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {str(e)}")
            self.minio_client = None
    
    def _get_content_hash(self, content: bytes) -> str:
        """Generate SHA-256 hash of content"""
        return hashlib.sha256(content).hexdigest()
    
    def _slugify(self, text: Optional[str]) -> str:
        if not text:
            return "default"
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip('-')
        return slug or "default"

    def _get_object_key(self, edition: Edition, page: EditionPage) -> str:
        """Generate MinIO object key for a page"""
        url_hash = hashlib.md5(page.url.encode()).hexdigest()[:8]
        extension = self._get_file_extension(page.url, page.format)

        publication_slug = self._slugify(getattr(edition, "publication", None))
        return f"{edition.date.isoformat()}/{publication_slug}_page_{page.page_number:03d}_{url_hash}{extension}"
    
    def _get_file_extension(self, url: str, format_type: str) -> str:
        """Determine file extension based on URL and format"""
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        if path.endswith('.pdf'):
            return '.pdf'
        elif format_type == 'pdf':
            return '.pdf'
        else:
            return '.html'
    
    def _download_with_proxy(self, url: str, max_retries: int = 3) -> Optional[bytes]:
        """Download content using proxy with retry logic and a final direct fallback.

        Strategy:
        - Try up to `max_retries` with rotating SmartProxy endpoints.
        - If all proxy attempts fail, try one direct request (no proxy) before giving up.
        """
        for attempt in range(max_retries):
            try:
                # Get random proxy
                proxy_config = self.settings.get_random_proxy()
                
                # Set up headers
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                
                logger.info(f"Downloading {url} (attempt {attempt + 1}/{max_retries})")
                
                response = requests.get(
                    url,
                    headers=headers,
                    proxies=proxy_config,
                    timeout=30,
                    allow_redirects=True
                )
                
                response.raise_for_status()
                
                logger.info(f"Successfully downloaded {len(response.content)} bytes from {url}")
                return response.content
                
            except requests.RequestException as e:
                logger.warning(f"Download attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                continue
        # Final direct (no-proxy) attempt
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            logger.info("All proxy attempts failed; trying direct download once for %s", url)
            resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            logger.info("Direct download succeeded (%d bytes) for %s", len(resp.content), url)
            return resp.content
        except requests.RequestException as e:
            logger.error(f"All {max_retries} proxy attempts and final direct attempt failed for {url}")
            logger.error("Direct attempt error: %s", e)
            return None
    
    def is_cached(self, edition: Edition, page: EditionPage) -> bool:
        """Check if page content is already cached in MinIO"""
        if not self.minio_client:
            return False

        object_key = self._get_object_key(edition, page)
        
        try:
            self.minio_client.stat_object(self.settings.minio_bucket, object_key)
            return True
        except S3Error:
            return False
    
    def cache_content(self, edition: Edition, page: EditionPage, content: bytes) -> bool:
        """Store content in MinIO cache"""
        if not self.minio_client:
            logger.error("MinIO client not available")
            return False

        object_key = self._get_object_key(edition, page)
        
        try:
            # Create metadata
            metadata = {
                'url': page.url,
                'page_number': str(page.page_number),
                'format': page.format,
                'content_hash': self._get_content_hash(content),
                'cached_at': datetime.utcnow().isoformat(),
            }
            
            if getattr(edition, "publication", None):
                metadata['publication'] = edition.publication
            if page.section:
                metadata['section'] = page.section
            if page.title:
                metadata['title'] = page.title
            
            # Upload to MinIO
            from io import BytesIO
            content_stream = BytesIO(content)
            
            self.minio_client.put_object(
                bucket_name=self.settings.minio_bucket,
                object_name=object_key,
                data=content_stream,
                length=len(content),
                metadata=metadata
            )
            
            logger.info(f"Cached {len(content)} bytes to {object_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache content: {str(e)}")
            return False
    
    def get_cached_content(self, edition: Edition, page: EditionPage) -> Optional[bytes]:
        """Retrieve content from MinIO cache"""
        if not self.minio_client:
            return None
        
        object_key = self._get_object_key(edition, page)
        
        try:
            response = self.minio_client.get_object(self.settings.minio_bucket, object_key)
            content = response.read()
            response.close()
            response.release_conn()
            
            logger.info(f"Retrieved {len(content)} bytes from cache: {object_key}")
            return content
            
        except S3Error as e:
            logger.warning(f"Content not found in cache: {object_key}")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve cached content: {str(e)}")
            return None
    
    def download_page(self, edition: Edition, page: EditionPage, force_refresh: bool = False) -> Optional[bytes]:
        """
        Download a single page, using cache if available.
        
        Args:
            edition_date: Date of the edition
            page: Page information
            force_refresh: Force download even if cached
            
        Returns:
            Content bytes if successful, None otherwise
        """
        # Check cache first (unless force refresh)
        if not force_refresh and self.is_cached(edition, page):
            content = self.get_cached_content(edition, page)
            if content:
                return content
        
        # Download fresh content
        content = self._download_with_proxy(page.url)
        
        if content:
            # Cache the downloaded content
            if self.cache_content(edition, page, content):
                logger.info(f"Downloaded and cached page {page.page_number}")
            else:
                logger.warning(f"Downloaded page {page.page_number} but caching failed")
            
            return content
        
        return None
    
    def download_edition(self, edition: Edition, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Download all pages in an edition.
        
        Args:
            edition: Edition to download
            force_refresh: Force download even if cached
            
        Returns:
            Dictionary with download results
        """
        results = {
            'edition_date': edition.date.isoformat(),
            'total_pages': edition.total_pages,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'cached_pages': 0,
            'downloaded_pages': [],
            'failed_pages': [],
            'start_time': datetime.utcnow().isoformat(),
            'publication': getattr(edition, 'publication', DEFAULT_PUBLICATION),
        }
        
        logger.info(f"Starting download of {edition.total_pages} pages for {edition.date} ({getattr(edition, 'publication', DEFAULT_PUBLICATION)})")
        
        # Parallelized page downloads (IO-bound)
        lock = Lock()
        max_workers = max(1, getattr(self.settings, 'scraper_parallelism', 4))

        def _task(p: EditionPage):
            try:
                was_cached = self.is_cached(edition, p)
                content = self.download_page(edition, p, force_refresh)
                with lock:
                    if content:
                        results['successful_downloads'] += 1
                        if was_cached and not force_refresh:
                            results['cached_pages'] += 1
                        results['downloaded_pages'].append({
                            'page_number': p.page_number,
                            'url': p.url,
                            'section': p.section,
                            'format': p.format,
                            'size_bytes': len(content),
                            'was_cached': was_cached and not force_refresh,
                            'publication': getattr(edition, 'publication', DEFAULT_PUBLICATION),
                        })
                        logger.info(f"Page {p.page_number}: Success ({len(content)} bytes)")
                    else:
                        results['failed_downloads'] += 1
                        results['failed_pages'].append({
                            'page_number': p.page_number,
                            'url': p.url,
                            'error': 'Download failed'
                        })
                        logger.error(f"Page {p.page_number}: Failed")
            except Exception as e:
                with lock:
                    results['failed_downloads'] += 1
                    results['failed_pages'].append({
                        'page_number': p.page_number,
                        'url': p.url,
                        'error': str(e)
                    })
                logger.error(f"Page {p.page_number}: Exception - {str(e)}")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_task, p) for p in edition.pages]
            for fut in as_completed(futures):
                _ = fut.result() if fut else None
        
        results['end_time'] = datetime.utcnow().isoformat()
        results['success_rate'] = results['successful_downloads'] / edition.total_pages if edition.total_pages > 0 else 0
        
        logger.info(f"Download complete: {results['successful_downloads']}/{edition.total_pages} successful (parallelism={max_workers})")
        
        return results
    
    def list_cached_editions(self) -> List[str]:
        """List all cached edition dates"""
        if not self.minio_client:
            return []
        
        try:
            objects = self.minio_client.list_objects(self.settings.minio_bucket)
            dates = set()
            
            for obj in objects:
                # Extract date from object key (format: YYYY-MM-DD/page_...)
                if '/' in obj.object_name:
                    date_part = obj.object_name.split('/')[0]
                    if len(date_part) == 10 and date_part.count('-') == 2:
                        dates.add(date_part)
            
            return sorted(list(dates))
            
        except Exception as e:
            logger.error(f"Failed to list cached editions: {str(e)}")
            return []
    
    def cleanup_old_cache(self, days_to_keep: int = 7) -> int:
        """
        Clean up cache entries older than specified days.
        
        Args:
            days_to_keep: Number of days to keep in cache
            
        Returns:
            Number of objects deleted
        """
        if not self.minio_client:
            return 0
        
        cutoff_date = datetime.utcnow().date()
        from datetime import timedelta
        cutoff_date = cutoff_date - timedelta(days=days_to_keep)
        
        deleted_count = 0
        
        try:
            objects = self.minio_client.list_objects(self.settings.minio_bucket)
            
            for obj in objects:
                # Extract date from object key
                if '/' in obj.object_name:
                    date_part = obj.object_name.split('/')[0]
                    try:
                        obj_date = datetime.strptime(date_part, '%Y-%m-%d').date()
                        if obj_date < cutoff_date:
                            self.minio_client.remove_object(self.settings.minio_bucket, obj.object_name)
                            deleted_count += 1
                            logger.info(f"Deleted old cache object: {obj.object_name}")
                    except ValueError:
                        # Skip objects that don't have valid date format
                        continue
            
            logger.info(f"Cleanup complete: {deleted_count} objects deleted")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {str(e)}")
            return 0


def main():
    """CLI interface for the downloader"""
    import argparse
    from .discover import EditionDiscoverer
    
    parser = argparse.ArgumentParser(description="Download e-edition content")
    parser.add_argument("--date", type=str, help="Date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--force", action="store_true", help="Force download even if cached")
    parser.add_argument("--cleanup", type=int, help="Clean up cache older than N days")
    parser.add_argument("--list-cache", action="store_true", help="List cached editions")
    parser.add_argument("--list-publications", action="store_true", help="List supported publications and exit")
    parser.add_argument("--publication", action="append", help="Specific publication/tab to download (may repeat)")
    parser.add_argument("--all-publications", action="store_true", help="Download all supported publications")
    parser.add_argument("--storage", type=str, default="storage_state.json", help="Session storage file")
    
    args = parser.parse_args()
    
    # Initialize downloader
    downloader = DownloadCache()
    
    discoverer = EditionDiscoverer(Path(args.storage))

    if args.list_publications:
        pubs = discoverer.get_available_publications()
        print("Available publications:")
        for pub in pubs:
            print(f"  {pub}")
        return

    if args.list_cache:
        cached_dates = downloader.list_cached_editions()
        print(f"Cached editions ({len(cached_dates)}):")
        for date_str in cached_dates:
            print(f"  {date_str}")
        return
    
    if args.cleanup:
        deleted = downloader.cleanup_old_cache(args.cleanup)
        print(f"Cleaned up {deleted} old cache entries")
        return
    
    # Parse date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            exit(1)
    else:
        target_date = date.today()
    
    # Determine publications to process
    publications: List[str]
    if args.all_publications:
        publications = discoverer.get_available_publications()
    elif args.publication:
        publications = args.publication
    else:
        publications = [DEFAULT_PUBLICATION]

    combined_results = []
    for pub in publications:
        edition = discoverer.discover_date(target_date, publication=pub)
        if not edition:
            print(f"No edition found for {target_date} ({pub})")
            continue

        results = downloader.download_edition(edition, force_refresh=args.force)
        combined_results.append(results)

        print(f"Download Results for {target_date} — {results['publication']}:")
        print(f"  Total pages: {results['total_pages']}")
        print(f"  Successful: {results['successful_downloads']}")
        print(f"  Failed: {results['failed_downloads']}")
        print(f"  From cache: {results['cached_pages']}")
        print(f"  Success rate: {results['success_rate']:.1%}")

        if results['failed_pages']:
            print("\nFailed pages:")
            for failed in results['failed_pages']:
                print(f"  Page {failed['page_number']}: {failed['error']}")
        print()

    if not combined_results:
        print("No editions were downloaded.")


if __name__ == "__main__":
    main()
