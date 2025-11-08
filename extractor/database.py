"""
Database module for news analyzer.

This module handles PostgreSQL database operations including:
- Article storage and retrieval
- Hash-based duplicate detection
- Processing history tracking
- Metadata management
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime, date, timezone
import hashlib
import json

import asyncpg
import asyncio
from asyncpg import Pool, Connection
from contextlib import asynccontextmanager

try:
    from .pdf_extractor import Article as PDFArticle
    from .html_extractor import HTMLArticle
    from .event_parser import extract_events
    from .normalize import normalize_section
except Exception:
    from pdf_extractor import Article as PDFArticle
    from html_extractor import HTMLArticle
    from event_parser import extract_events
    from normalize import normalize_section

logger = logging.getLogger(__name__)


@dataclass
class StoredArticle:
    """Represents an article stored in the database."""
    id: int
    title: str
    content: str
    content_hash: str
    url: Optional[str] = None
    source_type: str = 'unknown'  # 'pdf' or 'html'
    source_url: Optional[str] = None
    source_file: Optional[str] = None
    page_number: Optional[int] = None
    column_number: Optional[int] = None
    section: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None
    word_count: int = 0
    date_published: Optional[datetime] = None
    date_extracted: datetime = None
    date_created: datetime = None
    date_updated: datetime = None
    processing_status: str = 'extracted'  # 'extracted', 'summarized', 'notified'
    raw_html: Optional[str] = None
    metadata: Optional[Dict] = None
    location_name: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    event_dates: Optional[List[Dict]] = None
    
    def __post_init__(self):
        if not self.date_created:
            self.date_created = datetime.utcnow()
        if not self.date_updated:
            self.date_updated = datetime.utcnow()


class DatabaseManager:
    """Manage PostgreSQL database operations for news analyzer."""
    
    def __init__(self, database_url: str, pool_size: int = 10):
        """
        Initialize database manager.
        
        Args:
            database_url: PostgreSQL connection URL
            pool_size: Maximum number of connections in pool
        """
        self.database_url = database_url
        self.pool_size = pool_size
        self.pool: Optional[Pool] = None
    
    async def initialize(self):
        """Initialize database connection pool and create tables."""
        logger.info("Initializing database connection pool")
        
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=self.pool_size,
            command_timeout=60
        )
        
        await self.create_tables()
        logger.info("Database initialized successfully")
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool."""
        if not self.pool:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        async with self.pool.acquire() as connection:
            yield connection
    
    async def create_tables(self):
        """Create database tables if they don't exist."""
        schema_sql = """
        -- Extensions
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        
        -- Articles table
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            content_hash VARCHAR(32) UNIQUE NOT NULL,
            url TEXT,
            source_type VARCHAR(10) NOT NULL DEFAULT 'unknown',
            source_url TEXT,
            source_file TEXT,
            page_number INTEGER,
            column_number INTEGER,
            section VARCHAR(100),
            author VARCHAR(200),
            tags JSONB,
            word_count INTEGER NOT NULL DEFAULT 0,
            date_published TIMESTAMP WITH TIME ZONE,
            date_extracted TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            date_created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            date_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            processing_status VARCHAR(20) NOT NULL DEFAULT 'extracted',
            raw_html TEXT,
            metadata JSONB,
            location_name TEXT,
            location_lat DOUBLE PRECISION,
            location_lon DOUBLE PRECISION,
            event_dates JSONB
        );
        
        -- Summaries table
        CREATE TABLE IF NOT EXISTS summaries (
            id SERIAL PRIMARY KEY,
            article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            summary_text TEXT NOT NULL,
            summary_type VARCHAR(20) NOT NULL DEFAULT 'brief',
            model_used VARCHAR(50),
            tokens_used INTEGER,
            generation_time_ms INTEGER,
            date_created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            UNIQUE(article_id, summary_type)
        );
        
        -- Processing history table
        CREATE TABLE IF NOT EXISTS processing_history (
            id SERIAL PRIMARY KEY,
            date_processed DATE NOT NULL,
            source_type VARCHAR(10) NOT NULL,
            source_identifier TEXT NOT NULL,
            articles_found INTEGER NOT NULL DEFAULT 0,
            articles_new INTEGER NOT NULL DEFAULT 0,
            articles_duplicate INTEGER NOT NULL DEFAULT 0,
            processing_time_ms INTEGER,
            status VARCHAR(20) NOT NULL DEFAULT 'success',
            error_message TEXT,
            metadata JSONB,
            date_created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            UNIQUE(date_processed, source_type, source_identifier)
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
        CREATE INDEX IF NOT EXISTS idx_articles_date_published ON articles(date_published);
        CREATE INDEX IF NOT EXISTS idx_articles_date_extracted ON articles(date_extracted);
        CREATE INDEX IF NOT EXISTS idx_articles_source_type ON articles(source_type);
        CREATE INDEX IF NOT EXISTS idx_articles_processing_status ON articles(processing_status);
        CREATE INDEX IF NOT EXISTS idx_articles_section ON articles(section);
        CREATE INDEX IF NOT EXISTS idx_summaries_article_id ON summaries(article_id);
        CREATE INDEX IF NOT EXISTS idx_processing_history_date ON processing_history(date_processed);
        CREATE INDEX IF NOT EXISTS idx_processing_history_source ON processing_history(source_type, source_identifier);
        
        -- Full-text search index
        CREATE INDEX IF NOT EXISTS idx_articles_fts ON articles USING gin(to_tsvector('english', title || ' ' || content));

        -- Update trigger for date_updated
        CREATE OR REPLACE FUNCTION update_date_updated()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.date_updated = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trigger_articles_update_date ON articles;
        CREATE TRIGGER trigger_articles_update_date
            BEFORE UPDATE ON articles
            FOR EACH ROW
            EXECUTE FUNCTION update_date_updated();

        CREATE TABLE IF NOT EXISTS article_events (
            id SERIAL PRIMARY KEY,
            article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT,
            start_time TIMESTAMP WITH TIME ZONE,
            end_time TIMESTAMP WITH TIME ZONE,
            location_name TEXT,
            location_meta JSONB,
            date_created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            date_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_article_events_article_id ON article_events(article_id);
        CREATE INDEX IF NOT EXISTS idx_article_events_start_time ON article_events(start_time);
        """

        alter_sql = """
        ALTER TABLE articles ADD COLUMN IF NOT EXISTS raw_html TEXT;
        ALTER TABLE articles ADD COLUMN IF NOT EXISTS metadata JSONB;
        ALTER TABLE articles ADD COLUMN IF NOT EXISTS location_name TEXT;
        ALTER TABLE articles ADD COLUMN IF NOT EXISTS location_lat DOUBLE PRECISION;
        ALTER TABLE articles ADD COLUMN IF NOT EXISTS location_lon DOUBLE PRECISION;
        ALTER TABLE articles ADD COLUMN IF NOT EXISTS event_dates JSONB;
        """

        async with self.get_connection() as conn:
            await conn.execute(schema_sql)
            await conn.execute(alter_sql)
        
        logger.info("Database tables created/verified")
    
    async def store_articles(self, 
                           articles: List[Union[PDFArticle, HTMLArticle, StoredArticle]], 
                           source_identifier: str,
                           source_type: str = 'unknown') -> Tuple[int, int]:
        """
        Store articles in database with duplicate detection.
        
        Args:
            articles: List of articles to store
            source_identifier: Identifier for the source (filename, URL, etc.)
            source_type: Type of source ('pdf', 'html', etc.)
            
        Returns:
            Tuple of (new_articles_count, duplicate_articles_count)
        """
        start_time = datetime.utcnow()
        new_count = 0
        duplicate_count = 0
        
        logger.info(f"Storing {len(articles)} articles from {source_type} source: {source_identifier}")
        
        async with self.get_connection() as conn:
            async with conn.transaction():
                for article in articles:
                    # Convert article to StoredArticle format
                    stored_article = self._convert_to_stored_article(article, source_identifier, source_type)
                    
                    # Check for duplicates
                    existing_id = await self._find_duplicate(conn, stored_article.content_hash)
                    
                    if existing_id:
                        duplicate_count += 1
                        logger.debug(f"Duplicate article found: {stored_article.title[:50]}...")
                        await self._update_existing_article(conn, existing_id, stored_article)
                        continue

                    # Insert new article
                    article_id = await self._insert_article(conn, stored_article)
                    if stored_article.event_dates:
                        await self.store_article_events(conn, article_id, stored_article.event_dates)
                    new_count += 1
                    logger.debug(f"Stored new article (ID {article_id}): {stored_article.title[:50]}...")

                # Record processing history
                processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                await self._record_processing_history(
                    conn,
                    date.today(),
                    source_type,
                    source_identifier,
                    len(articles),
                    new_count,
                    duplicate_count,
                    processing_time_ms
                )
        
        logger.info(f"Storage complete: {new_count} new, {duplicate_count} duplicates")
        return new_count, duplicate_count
    
    async def _find_duplicate(self, conn: Connection, content_hash: str) -> Optional[int]:
        """Find existing article by content hash."""
        result = await conn.fetchrow(
            "SELECT id FROM articles WHERE content_hash = $1",
            content_hash
        )
        return result['id'] if result else None
    
    async def _insert_article(self, conn: Connection, article: StoredArticle) -> int:
        """Insert new article and return its ID."""
        sql = """
        INSERT INTO articles (
            title, content, content_hash, url, source_type, source_url, source_file,
            page_number, column_number, section, author, tags, word_count,
            date_published, date_extracted, processing_status,
            raw_html, metadata, location_name, location_lat, location_lon, event_dates
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
            $14, $15, $16, $17, $18, $19, $20, $21, $22
        ) RETURNING id
        """
        
        tags_json = json.dumps(article.tags) if article.tags else None
        metadata_json = json.dumps(article.metadata) if article.metadata else None
        event_dates_json = json.dumps(article.event_dates) if article.event_dates else None
        
        result = await conn.fetchrow(
            sql,
            article.title,
            article.content,
            article.content_hash,
            article.url,
            article.source_type,
            article.source_url,
            article.source_file,
            article.page_number,
            article.column_number,
            article.section,
            article.author,
            tags_json,
            article.word_count,
            article.date_published,
            article.date_extracted,
            article.processing_status,
            article.raw_html,
            metadata_json,
            article.location_name,
            article.location_lat,
            article.location_lon,
            event_dates_json
        )
        
        return result['id']
    
    async def _record_processing_history(self, 
                                       conn: Connection,
                                       date_processed: date,
                                       source_type: str,
                                       source_identifier: str,
                                       articles_found: int,
                                       articles_new: int,
                                       articles_duplicate: int,
                                       processing_time_ms: int,
                                       status: str = 'success',
                                       error_message: Optional[str] = None,
                                       metadata: Optional[Dict] = None):
        """Record processing history entry."""
        sql = """
        INSERT INTO processing_history (
            date_processed, source_type, source_identifier, articles_found,
            articles_new, articles_duplicate, processing_time_ms, status,
            error_message, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (date_processed, source_type, source_identifier)
        DO UPDATE SET
            articles_found = EXCLUDED.articles_found,
            articles_new = EXCLUDED.articles_new,
            articles_duplicate = EXCLUDED.articles_duplicate,
            processing_time_ms = EXCLUDED.processing_time_ms,
            status = EXCLUDED.status,
            error_message = EXCLUDED.error_message,
            metadata = EXCLUDED.metadata
        """
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        await conn.execute(
            sql,
            date_processed,
            source_type,
            source_identifier,
            articles_found,
            articles_new,
            articles_duplicate,
            processing_time_ms,
            status,
            error_message,
            metadata_json
        )

    async def _update_existing_article(self,
                                      conn: Connection,
                                      article_id: int,
                                      new_article: StoredArticle) -> None:
        """Merge new extraction metadata into an existing article record."""
        row = await conn.fetchrow(
            """
            SELECT section, author, tags, word_count, page_number, column_number,
                   date_published, metadata, raw_html, location_name, location_lat,
                   location_lon, source_file, source_url, event_dates
            FROM articles WHERE id = $1
            """,
            article_id,
        )
        if not row:
            return

        existing = dict(row)

        existing_tags = self._ensure_list(existing.get('tags'))
        incoming_tags = new_article.tags or []
        merged_tags = self._merge_tags(existing_tags, incoming_tags)
        tags_json = json.dumps(merged_tags) if merged_tags else None

        existing_meta = self._ensure_dict(existing.get('metadata'))
        merged_meta = self._merge_metadata(existing_meta, new_article.metadata)
        metadata_json = json.dumps(merged_meta) if merged_meta else None

        section = new_article.section or existing.get('section')
        author = new_article.author or existing.get('author')
        word_count = new_article.word_count or existing.get('word_count') or 0
        page_number = new_article.page_number if new_article.page_number is not None else existing.get('page_number')
        column_number = new_article.column_number if new_article.column_number is not None else existing.get('column_number')
        date_published = new_article.date_published or existing.get('date_published')

        raw_html = new_article.raw_html if new_article.raw_html else existing.get('raw_html')
        location_name = new_article.location_name or existing.get('location_name')
        location_lat = new_article.location_lat if new_article.location_lat is not None else existing.get('location_lat')
        location_lon = new_article.location_lon if new_article.location_lon is not None else existing.get('location_lon')
        source_file = existing.get('source_file') or new_article.source_file
        source_url = existing.get('source_url') or new_article.source_url

        existing_events = self._ensure_event_list(existing.get('event_dates'))
        merged_events = existing_events
        if new_article.event_dates:
            merged_events = self._merge_event_lists(existing_events, new_article.event_dates)
            if merged_events:
                await self.store_article_events(conn, article_id, merged_events)
        event_dates_json = json.dumps(merged_events) if merged_events else None

        await conn.execute(
            """
            UPDATE articles
            SET section = $1,
                author = $2,
                tags = $3,
                word_count = $4,
                page_number = $5,
                column_number = $6,
                date_published = $7,
                metadata = $8,
                raw_html = $9,
                location_name = $10,
                location_lat = $11,
                location_lon = $12,
                source_file = $13,
                source_url = $14,
                event_dates = $15
            WHERE id = $16
            """,
            section,
            author,
            tags_json,
            word_count,
            page_number,
            column_number,
            date_published,
            metadata_json,
            raw_html,
            location_name,
            location_lat,
            location_lon,
            source_file,
            source_url,
            event_dates_json,
            article_id,
        )

    def _ensure_list(self, value: Optional[Union[str, List]]) -> List:
        if not value:
            return []
        if isinstance(value, list):
            return value
        try:
            return json.loads(value) if value else []
        except Exception:
            return []

    def _ensure_event_list(self, value: Optional[Union[str, List]]) -> List[Dict]:
        raw = self._ensure_list(value)
        return [item for item in raw if isinstance(item, dict)]

    def _ensure_dict(self, value: Optional[Union[str, Dict]]) -> Dict:
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    def _merge_metadata(self, existing: Dict, new_metadata: Optional[Dict]) -> Dict:
        if not new_metadata:
            return existing
        merged = existing.copy()
        for key, value in new_metadata.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return merged

    def _merge_tags(self, existing: List[str], incoming: List[str]) -> List[str]:
        combined = []
        for tag in (existing or []):
            norm = tag.strip()
            if norm and norm not in combined:
                combined.append(norm)
        for tag in (incoming or []):
            norm = str(tag).strip()
            if norm and norm not in combined:
                combined.append(norm)
        return combined

    def _merge_event_lists(self, existing: List[Dict], new_events: Optional[List[Dict]]) -> List[Dict]:
        if not new_events:
            return existing
        seen = {json.dumps(evt, sort_keys=True): evt for evt in existing or []}
        for evt in new_events:
            if not isinstance(evt, dict):
                continue
            key = json.dumps(evt, sort_keys=True)
            seen[key] = evt
        return list(seen.values())

    def _attach_events(self, article: StoredArticle) -> None:
        try:
            events = extract_events(article.content)
        except Exception as exc:
            logger.debug(f"Event extraction failed for article {article.title[:40]}: {exc}")
            events = []

        if events:
            article.event_dates = events
            if not article.metadata:
                article.metadata = {}
            article.metadata.setdefault('events', events)
            if not article.location_name:
                for event in events:
                    if event.get('location_name'):
                        article.location_name = event['location_name']
                        break

    def _normalize_datetime(self, value: Union[str, datetime, date, None]) -> Optional[datetime]:
        """Convert various date-like values to timezone-aware datetimes for storage."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, date):
            combined = datetime.combine(value, datetime.min.time())
            return combined.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                try:
                    dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    logger.debug("Failed to parse datetime string '%s'", value)
                    return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return None

    async def store_article_events(self, conn: Connection, article_id: int, events: List[Dict]) -> None:
        await conn.execute("DELETE FROM article_events WHERE article_id = $1", article_id)
        for event in events:
            start_time = self._normalize_datetime(event.get('start_time'))
            end_time = self._normalize_datetime(event.get('end_time'))
            await conn.execute(
                """
                INSERT INTO article_events (
                    article_id, title, description, start_time, end_time,
                    location_name, location_meta
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                article_id,
                event.get('title') or 'Community Event',
                event.get('context'),
                start_time,
                end_time,
                event.get('location_name'),
                json.dumps(event) if event else None,
            )

    def _convert_to_stored_article(self, 
                                 article: Union[PDFArticle, HTMLArticle, StoredArticle],
                                 source_identifier: str,
                                 source_type: str) -> StoredArticle:
        """Convert article to StoredArticle format."""
        if isinstance(article, StoredArticle):
            return article
        
        # Generate content hash
        content_hash = hashlib.md5(
            f"{article.title}{article.content}".encode('utf-8')
        ).hexdigest()
        
        if isinstance(article, PDFArticle):
            stored = StoredArticle(
                id=0,  # Will be set by database
                title=article.title,
                content=article.content,
                content_hash=content_hash,
                source_type='pdf',
                source_file=source_identifier,
                page_number=article.page_number,
                column_number=article.column,
                section=normalize_section(article.section),
                word_count=article.word_count,
                date_published=article.date_published,
                date_extracted=datetime.utcnow(),
                metadata={
                    'bounds': {
                        'x0': article.x0,
                        'y0': article.y0,
                        'x1': article.x1,
                        'y1': article.y1,
                    }
                }
            )
            self._attach_events(stored)
            return stored
        elif isinstance(article, HTMLArticle):
            stored = StoredArticle(
                id=0,  # Will be set by database
                title=article.title,
                content=article.content,
                content_hash=content_hash,
                url=article.url,
                source_type='html',
                source_url=source_identifier,
                section=normalize_section(article.section),
                author=article.author,
                tags=article.tags,
                word_count=article.word_count,
                date_published=article.date_published,
                date_extracted=datetime.utcnow(),
                raw_html=article.raw_html,
                metadata={'tags': article.tags} if article.tags else None,
                location_name=getattr(article, 'location_name', None),
                location_lat=getattr(article, 'location_lat', None),
                location_lon=getattr(article, 'location_lon', None),
                event_dates=getattr(article, 'event_dates', None)
            )
            self._attach_events(stored)
            return stored
        else:
            raise ValueError(f"Unsupported article type: {type(article)}")
    
    async def get_articles_for_processing(self, 
                                        processing_status: str = 'extracted',
                                        limit: int = 100) -> List[StoredArticle]:
        """Get articles ready for processing (e.g., summarization)."""
        sql = """
        SELECT * FROM articles 
        WHERE processing_status = $1
        ORDER BY date_extracted ASC
        LIMIT $2
        """
        
        async with self.get_connection() as conn:
            rows = await conn.fetch(sql, processing_status, limit)
            
            articles = []
            for row in rows:
                tags = json.loads(row['tags']) if row['tags'] else None
                
                article = StoredArticle(
                    id=row['id'],
                    title=row['title'],
                    content=row['content'],
                    content_hash=row['content_hash'],
                    url=row['url'],
                    source_type=row['source_type'],
                    source_url=row['source_url'],
                    source_file=row['source_file'],
                    page_number=row['page_number'],
                    column_number=row['column_number'],
                    section=row['section'],
                    author=row['author'],
                    tags=tags,
                    word_count=row['word_count'],
                    date_published=row['date_published'],
                    date_extracted=row['date_extracted'],
                    date_created=row['date_created'],
                    date_updated=row['date_updated'],
                    processing_status=row['processing_status']
                )
                articles.append(article)
            
            return articles
    
    async def update_processing_status(self, article_id: int, status: str):
        """Update the processing status of an article."""
        sql = "UPDATE articles SET processing_status = $1 WHERE id = $2"
        
        async with self.get_connection() as conn:
            await conn.execute(sql, status, article_id)
    
    async def store_summary(self, 
                          article_id: int, 
                          summary: str, 
                          key_points: List[str], 
                          sentiment: Optional[str] = None,
                          confidence_score: float = 0.8,
                          tokens_used: int = 0,
                          processing_time_ms: int = 0,
                          model_used: str = "gpt-4o-mini") -> int:
        """Store article summary in database."""
        sql = """
        INSERT INTO summaries (
            article_id, summary_text, summary_type, model_used, 
            tokens_used, generation_time_ms
        ) VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (article_id, summary_type) 
        DO UPDATE SET
            summary_text = EXCLUDED.summary_text,
            model_used = EXCLUDED.model_used,
            tokens_used = EXCLUDED.tokens_used,
            generation_time_ms = EXCLUDED.generation_time_ms
        RETURNING id
        """
        
        # Combine summary with key points and sentiment
        full_summary = summary
        if key_points:
            full_summary += "\n\nKey Points:\n" + "\n".join(f"• {point}" for point in key_points)
        if sentiment:
            full_summary += f"\n\nSentiment: {sentiment}"
        
        async with self.get_connection() as conn:
            result = await conn.fetchrow(
                sql, 
                article_id, 
                full_summary, 
                'brief', 
                model_used, 
                tokens_used, 
                processing_time_ms
            )
            return result['id']
    
    async def get_processing_stats(self, days: int = 7) -> Dict:
        """Get processing statistics for the last N days."""
        sql = """
        SELECT 
            date_processed,
            source_type,
            SUM(articles_found) as total_found,
            SUM(articles_new) as total_new,
            SUM(articles_duplicate) as total_duplicates,
            AVG(processing_time_ms) as avg_processing_time
        FROM processing_history 
        WHERE date_processed >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY date_processed, source_type
        ORDER BY date_processed DESC, source_type
        """
        
        async with self.get_connection() as conn:
            rows = await conn.fetch(sql % days)
            
            stats = []
            for row in rows:
                stats.append(dict(row))
            
            return {
                'period_days': days,
                'daily_stats': stats,
                'summary': {
                    'total_found': sum(s['total_found'] for s in stats),
                    'total_new': sum(s['total_new'] for s in stats),
                    'total_duplicates': sum(s['total_duplicates'] for s in stats),
                }
            }
    
    async def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old processing history data."""
        sql = """
        DELETE FROM processing_history 
        WHERE date_processed < CURRENT_DATE - INTERVAL '%s days'
        """
        
        async with self.get_connection() as conn:
            result = await conn.execute(sql % days_to_keep)
            # Extract count from result string like "DELETE 5"
            deleted_count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
            
            logger.info(f"Cleaned up {deleted_count} old processing history records")
            return deleted_count


async def main():
    """CLI interface for database operations."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Database operations for news analyzer")
    parser.add_argument("--init", action="store_true", help="Initialize database tables")
    parser.add_argument("--stats", type=int, default=7, help="Show processing stats for N days")
    parser.add_argument("--cleanup", type=int, help="Clean up data older than N days")
    parser.add_argument("--database-url", help="Database URL (default: from DATABASE_URL env)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Get database URL
    database_url = args.database_url or os.getenv('DATABASE_URL')
    if not database_url:
        print("Error: DATABASE_URL environment variable or --database-url argument required")
        exit(1)
    
    # Initialize database manager
    db_manager = DatabaseManager(database_url)
    
    try:
        await db_manager.initialize()
        
        if args.init:
            print("Database tables initialized successfully")
        
        if args.stats:
            stats = await db_manager.get_processing_stats(args.stats)
            print(f"\nProcessing Statistics (last {args.stats} days):")
            print(f"Total found: {stats['summary']['total_found']}")
            print(f"Total new: {stats['summary']['total_new']}")
            print(f"Total duplicates: {stats['summary']['total_duplicates']}")
            
            print("\nDaily breakdown:")
            for stat in stats['daily_stats']:
                print(f"  {stat['date_processed']} ({stat['source_type']}): "
                      f"{stat['total_new']} new, {stat['total_duplicates']} duplicates")
        
        if args.cleanup:
            deleted = await db_manager.cleanup_old_data(args.cleanup)
            print(f"Cleaned up {deleted} old records")
    
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
