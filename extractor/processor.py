"""
Unified extraction processor for news analyzer.

This module coordinates the extraction process by:
- Processing cached content from the scraper
- Routing to appropriate extractors (PDF/HTML)
- Storing results in PostgreSQL with deduplication
- Tracking processing history
"""

import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime, date
import json
import os
import sys
from minio import Minio
from minio.error import S3Error

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from extractor.pdf_extractor import PDFExtractor, Article as PDFArticle
    from extractor.html_extractor import HTMLExtractor, HTMLArticle
    from extractor.database import DatabaseManager, StoredArticle
except Exception:
    from pdf_extractor import PDFExtractor, Article as PDFArticle
    from html_extractor import HTMLExtractor, HTMLArticle
    from database import DatabaseManager, StoredArticle

# Canonical config source lives in this component
try:
    from extractor.config import Settings
except Exception:
    from config import Settings

logger = logging.getLogger(__name__)


class ExtractionProcessor:
    """Main processor for coordinating text extraction and storage."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize extraction processor.
        
        Args:
            database_url: PostgreSQL connection URL (uses environment if not provided)
        """
        self.settings = Settings()
        
        # Initialize extractors
        self.pdf_extractor = PDFExtractor()
        self.html_extractor = HTMLExtractor(include_raw_html=True)
        
        # Initialize database manager
        db_url = database_url or self.settings.database_url
        self.db_manager = DatabaseManager(db_url)
        
        # Initialize MinIO client for cache access
        self.minio_client = None
        if self.settings.minio_endpoint:
            self.minio_client = Minio(
                self.settings.minio_endpoint,
                access_key=self.settings.minio_access_key,
                secret_key=self.settings.minio_secret_key,
                secure=False  # Assuming local deployment
            )
    
    async def initialize(self):
        """Initialize the processor components."""
        logger.info("Initializing extraction processor")
        await self.db_manager.initialize()
        logger.info("Extraction processor ready")
    
    async def close(self):
        """Clean up processor resources."""
        await self.db_manager.close()
        logger.info("Extraction processor closed")
    
    async def process_cached_edition(self, edition_date: date, force_reprocess: bool = False) -> Dict:
        """
        Process all cached content for a specific edition date.
        
        Args:
            edition_date: Date of edition to process
            force_reprocess: Whether to reprocess already processed content
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing cached edition for {edition_date}")
        
        if not self.minio_client:
            raise RuntimeError("MinIO client not configured")
        
        start_time = datetime.utcnow()
        results = {
            'edition_date': edition_date.isoformat(),
            'total_files': 0,
            'processed_files': 0,
            'skipped_files': 0,
            'failed_files': 0,
            'total_articles': 0,
            'new_articles': 0,
            'duplicate_articles': 0,
            'processing_time_ms': 0,
            'files': []
        }
        
        try:
            # List cached objects for this date
            date_prefix = edition_date.strftime('%Y-%m-%d')
            objects = self.minio_client.list_objects(
                self.settings.minio_bucket,
                prefix=f"{date_prefix}/"
            )
            
            cached_files = list(objects)
            results['total_files'] = len(cached_files)
            
            if not cached_files:
                logger.warning(f"No cached files found for {edition_date}")
                return results
            
            # Process each cached file
            for obj in cached_files:
                file_result = await self._process_cached_file(obj.object_name, force_reprocess)
                results['files'].append(file_result)
                
                if file_result['status'] == 'processed':
                    results['processed_files'] += 1
                    results['total_articles'] += file_result['articles_found']
                    results['new_articles'] += file_result['articles_new']
                    results['duplicate_articles'] += file_result['articles_duplicate']
                elif file_result['status'] == 'skipped':
                    results['skipped_files'] += 1
                else:
                    results['failed_files'] += 1
            
            # Calculate processing time
            end_time = datetime.utcnow()
            results['processing_time_ms'] = int((end_time - start_time).total_seconds() * 1000)
            
            logger.info(f"Edition processing complete: {results['new_articles']} new articles, "
                       f"{results['duplicate_articles']} duplicates from {results['processed_files']} files")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to process cached edition {edition_date}: {str(e)}")
            raise
    
    async def _process_cached_file(self, object_name: str, force_reprocess: bool = False) -> Dict:
        """
        Process a single cached file.
        
        Args:
            object_name: MinIO object name
            force_reprocess: Whether to reprocess if already done
            
        Returns:
            Dictionary with file processing results
        """
        file_result = {
            'object_name': object_name,
            'file_type': 'unknown',
            'status': 'failed',
            'articles_found': 0,
            'articles_new': 0,
            'articles_duplicate': 0,
            'error_message': None,
            'processing_time_ms': 0
        }
        
        start_time = datetime.utcnow()
        
        try:
            logger.debug(f"Processing cached file: {object_name}")
            
            # Check if already processed (unless force reprocess)
            if not force_reprocess:
                # Extract date and identifier from object name for checking
                parts = object_name.split('/')
                if len(parts) >= 2:
                    date_str = parts[0]
                    file_identifier = '/'.join(parts[1:])
                    
                    try:
                        process_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        
                        # Check processing history
                        stats = await self.db_manager.get_processing_stats(1)
                        for stat in stats['daily_stats']:
                            if (stat['date_processed'] == process_date and 
                                file_identifier in str(stat)):
                                file_result['status'] = 'skipped'
                                file_result['error_message'] = 'Already processed'
                                return file_result
                    except ValueError:
                        pass  # Invalid date format, continue processing
            
            # Retrieve metadata and download file content
            metadata = {}
            try:
                stat = self.minio_client.stat_object(self.settings.minio_bucket, object_name)
                if stat.metadata:
                    metadata = {k.lower(): v for k, v in stat.metadata.items()}
            except S3Error as meta_err:
                logger.debug(f"No metadata for {object_name}: {meta_err}")

            content = self._download_cached_file(object_name)
            if not content:
                file_result['error_message'] = 'Failed to download content'
                return file_result
            
            # Determine file type and extract
            file_type = self._determine_file_type(object_name, content)
            file_result['file_type'] = file_type
            
            articles = []
            if file_type == 'pdf':
                articles = self.pdf_extractor.extract_from_bytes(content, object_name)
            elif file_type == 'html':
                html_content = content.decode('utf-8', errors='ignore')
                articles = self.html_extractor.extract_from_html(html_content, object_name)
            else:
                file_result['error_message'] = f'Unsupported file type: {file_type}'
                return file_result
            
            file_result['articles_found'] = len(articles)

            if articles:
                publication = (
                    metadata.get('publication')
                    or metadata.get('x-amz-meta-publication')
                )
                if publication:
                    for article in articles:
                        if hasattr(article, 'metadata'):
                            article.metadata = article.metadata or {}
                            article.metadata['publication'] = publication
                        if hasattr(article, 'section') and not article.section:
                            article.section = publication
                # Store articles in database
                new_count, duplicate_count = await self.db_manager.store_articles(
                    articles, object_name, file_type
                )
                
                file_result['articles_new'] = new_count
                file_result['articles_duplicate'] = duplicate_count
                file_result['status'] = 'processed'
            else:
                file_result['status'] = 'processed'
                file_result['error_message'] = 'No articles extracted'
            
            # Calculate processing time
            end_time = datetime.utcnow()
            file_result['processing_time_ms'] = int((end_time - start_time).total_seconds() * 1000)
            
            logger.debug(f"Processed {object_name}: {file_result['articles_new']} new, "
                        f"{file_result['articles_duplicate']} duplicate articles")
            
            return file_result
            
        except Exception as e:
            file_result['error_message'] = str(e)
            logger.error(f"Failed to process {object_name}: {str(e)}")
            return file_result
    
    def _download_cached_file(self, object_name: str) -> Optional[bytes]:
        """Download file content from MinIO cache."""
        try:
            response = self.minio_client.get_object(self.settings.minio_bucket, object_name)
            content = response.read()
            response.close()
            response.release_conn()
            return content
        except S3Error as e:
            logger.error(f"Failed to download {object_name}: {str(e)}")
            return None
    
    def _determine_file_type(self, object_name: str, content: bytes) -> str:
        """Determine file type from object name and content."""
        # Check file extension
        if object_name.lower().endswith('.pdf'):
            return 'pdf'
        elif object_name.lower().endswith(('.html', '.htm')):
            return 'html'
        
        # Check content magic bytes
        if content.startswith(b'%PDF'):
            return 'pdf'
        elif b'<html' in content[:1000].lower() or b'<!doctype html' in content[:1000].lower():
            return 'html'
        
        # Default to HTML for web content
        return 'html'
    
    async def process_file(self, file_path: Path, source_type: Optional[str] = None) -> Dict:
        """
        Process a single file directly.
        
        Args:
            file_path: Path to file to process
            source_type: Override file type detection
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing file: {file_path}")
        
        start_time = datetime.utcnow()
        
        try:
            # Determine file type
            if source_type:
                file_type = source_type
            elif file_path.suffix.lower() == '.pdf':
                file_type = 'pdf'
            elif file_path.suffix.lower() in ['.html', '.htm']:
                file_type = 'html'
            else:
                raise ValueError(f"Unsupported file type: {file_path.suffix}")
            
            # Extract articles
            articles = []
            if file_type == 'pdf':
                articles = self.pdf_extractor.extract_from_file(file_path)
            elif file_type == 'html':
                articles = self.html_extractor.extract_from_file(file_path)
            
            # Store in database
            new_count, duplicate_count = await self.db_manager.store_articles(
                articles, str(file_path), file_type
            )
            
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            result = {
                'file_path': str(file_path),
                'file_type': file_type,
                'articles_found': len(articles),
                'articles_new': new_count,
                'articles_duplicate': duplicate_count,
                'processing_time_ms': processing_time_ms,
                'status': 'success'
            }
            
            logger.info(f"File processing complete: {new_count} new, {duplicate_count} duplicate articles")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {str(e)}")
            return {
                'file_path': str(file_path),
                'file_type': source_type or 'unknown',
                'articles_found': 0,
                'articles_new': 0,
                'articles_duplicate': 0,
                'processing_time_ms': 0,
                'status': 'failed',
                'error_message': str(e)
            }
    
    async def get_articles_for_summarization(self, limit: int = 100) -> List[StoredArticle]:
        """Get articles ready for summarization."""
        return await self.db_manager.get_articles_for_processing('extracted', limit)
    
    async def mark_article_summarized(self, article_id: int):
        """Mark an article as summarized."""
        await self.db_manager.update_processing_status(article_id, 'summarized')
    
    async def get_processing_stats(self, days: int = 7) -> Dict:
        """Get processing statistics."""
        return await self.db_manager.get_processing_stats(days)


async def main():
    """CLI interface for extraction processor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Text extraction processor for news analyzer")
    parser.add_argument("--date", type=str, help="Process cached edition for date (YYYY-MM-DD)")
    parser.add_argument("--file", type=str, help="Process single file")
    parser.add_argument("--force", action="store_true", help="Force reprocessing")
    parser.add_argument("--stats", type=int, default=7, help="Show processing stats for N days")
    parser.add_argument("--type", choices=['pdf', 'html'], help="Override file type detection")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Initialize processor
    processor = ExtractionProcessor()
    
    try:
        await processor.initialize()
        
        if args.date:
            # Process cached edition
            try:
                target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
            except ValueError:
                print(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
                exit(1)
            
            results = await processor.process_cached_edition(target_date, args.force)
            
            print(f"Edition Processing Results for {target_date}:")
            print(f"  Files processed: {results['processed_files']}/{results['total_files']}")
            print(f"  Articles found: {results['total_articles']}")
            print(f"  New articles: {results['new_articles']}")
            print(f"  Duplicates: {results['duplicate_articles']}")
            print(f"  Processing time: {results['processing_time_ms']}ms")
            
            if results['failed_files'] > 0:
                print(f"  Failed files: {results['failed_files']}")
                for file_result in results['files']:
                    if file_result['status'] == 'failed':
                        print(f"    {file_result['object_name']}: {file_result['error_message']}")
        
        elif args.file:
            # Process single file
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"File not found: {file_path}")
                exit(1)
            
            result = await processor.process_file(file_path, args.type)
            
            print(f"File Processing Results:")
            print(f"  File: {result['file_path']}")
            print(f"  Type: {result['file_type']}")
            print(f"  Articles found: {result['articles_found']}")
            print(f"  New articles: {result['articles_new']}")
            print(f"  Duplicates: {result['articles_duplicate']}")
            print(f"  Status: {result['status']}")
            
            if result['status'] == 'failed':
                print(f"  Error: {result['error_message']}")
        
        # Show stats
        if args.stats:
            stats = await processor.get_processing_stats(args.stats)
            print(f"\nProcessing Statistics (last {args.stats} days):")
            print(f"  Total articles found: {stats['summary']['total_found']}")
            print(f"  New articles: {stats['summary']['total_new']}")
            print(f"  Duplicates: {stats['summary']['total_duplicates']}")
    
    finally:
        await processor.close()


if __name__ == "__main__":
    asyncio.run(main())
