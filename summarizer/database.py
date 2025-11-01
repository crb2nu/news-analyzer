"""
Database module for news analyzer summarizer service.

This module handles PostgreSQL database operations for the summarizer including:
- Article retrieval for summarization
- Summary storage
- Processing status updates
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, date, timedelta
import json

import asyncpg
from asyncpg import Pool, Connection, exceptions
from contextlib import asynccontextmanager

try:
    from summarizer.utils import derive_fallback_title
except ImportError:
    from utils import derive_fallback_title

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
    """Manage PostgreSQL database operations for summarizer service."""
    
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
        """Initialize database connection pool."""
        logger.info("Initializing database connection pool")
        
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=self.pool_size,
            command_timeout=60
        )
        
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
    
    async def get_articles_for_processing(self, 
                                        processing_status: str = 'extracted',
                                        limit: int = 100,
                                        article_id: Optional[int] = None) -> List[StoredArticle]:
        """Get articles ready for processing (e.g., summarization)."""
        if article_id:
            sql = """
            SELECT * FROM articles 
            WHERE id = $1
            LIMIT 1
            """
            params = [article_id]
        else:
            sql = """
            SELECT * FROM articles 
            WHERE processing_status = $1
            ORDER BY date_extracted ASC
            LIMIT $2
            """
            params = [processing_status, limit]
        
        async with self.get_connection() as conn:
            rows = await conn.fetch(sql, *params)
            
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
                    processing_status=row['processing_status'],
                    raw_html=row.get('raw_html'),
                    metadata=json.loads(row.get('metadata')) if row.get('metadata') else None,
                    location_name=row.get('location_name'),
                    location_lat=row.get('location_lat'),
                    location_lon=row.get('location_lon'),
                    event_dates=json.loads(row.get('event_dates')) if row.get('event_dates') else None
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

    async def get_feed_dates(self, limit: int = 14) -> List[Dict]:
        """Return recent dates that have extracted/summarized articles with counts.

        Args:
            limit: number of most recent days to return

        Returns:
            List of dicts with keys: date, total, summarized
        """
        sql = """
        SELECT
            DATE(a.date_extracted) AS day,
            COUNT(*) AS total,
            SUM(CASE WHEN a.processing_status = 'summarized' THEN 1 ELSE 0 END) AS summarized
        FROM articles a
        GROUP BY day
        ORDER BY day DESC
        LIMIT $1
        """

        async with self.get_connection() as conn:
            rows = await conn.fetch(sql, limit)
            return [
                {
                    'date': row['day'].isoformat(),
                    'total': row['total'],
                    'summarized': row['summarized'],
                }
                for row in rows
            ]

    async def get_feed_articles(
        self,
        target_date: date,
        limit: int = 50,
        section: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict]:
        """Return articles with their brief summaries for a given date.

        Joins articles to summaries (prefers summary_type = 'brief').
        """
        params: List = [target_date]
        filters = ["DATE(a.date_extracted) = $1"]

        if section:
            params.append(section)
            filters.append(f"a.section = ${len(params)}")

        if search:
            # Simple ILIKE search over title/content
            params.append(f"%{search}%")
            params.append(f"%{search}%")
            filters.append(
                f"(a.title ILIKE ${len(params)-1} OR a.content ILIKE ${len(params)})"
            )

        params.append(limit)

        sql = f"""
        SELECT
            a.id,
            a.title,
            a.section,
            a.url,
            a.source_url,
            a.source_file,
            a.page_number,
            a.date_published,
            a.word_count,
            a.location_name,
            a.location_lat,
            a.location_lon,
            a.event_dates,
            a.content,
            COALESCE(s.summary_text, '') AS summary_text
        FROM articles a
        LEFT JOIN LATERAL (
            SELECT summary_text
            FROM summaries s
            WHERE s.article_id = a.id AND s.summary_type = 'brief'
            ORDER BY s.date_created DESC
            LIMIT 1
        ) s ON TRUE
        WHERE {' AND '.join(filters)}
        ORDER BY COALESCE(a.date_published, a.date_extracted) DESC, a.id DESC
        LIMIT ${len(params)}
        """

        async with self.get_connection() as conn:
            rows = await conn.fetch(sql, *params)
            results: List[Dict] = []
            for row in rows:
                source_path = row['source_url'] or row['url'] or row['source_file']
                title = derive_fallback_title(
                    row['title'],
                    row['content'],
                    source_path,
                    row['page_number']
                )
                article_url = f"/articles/{row['id']}/source" if source_path else None

                section = row['section'] or 'General'
                section_numeric = section.replace(' ', '').isdigit()
                section = section if section and not section_numeric else 'General'

                event_dates = row['event_dates']
                if isinstance(event_dates, str):
                    try:
                        event_dates = json.loads(event_dates)
                    except json.JSONDecodeError:
                        event_dates = []

                results.append({
                    'id': row['id'],
                    'title': title,
                    'section': section,
                    'summary': row['summary_text'] or '',
                    'url': article_url,
                    'date_published': row['date_published'].isoformat() if row['date_published'] else None,
                    'word_count': row['word_count'],
                    'source_path': source_path,
                    'page_number': row['page_number'],
                    'location_name': row['location_name'],
                    'location_lat': row['location_lat'],
                    'location_lon': row['location_lon'],
                    'events': event_dates if event_dates else [],
                })
            return results

    async def get_article_by_id(self, article_id: int) -> Optional[Dict]:
        sql_article = """
        SELECT a.*, COALESCE(s.summary_text, '') AS summary_text
        FROM articles a
        LEFT JOIN summaries s ON s.article_id = a.id AND s.summary_type = 'brief'
        WHERE a.id = $1
        """

        sql_events = """
        SELECT id, title, description, start_time, end_time, location_name, location_meta
        FROM article_events
        WHERE article_id = $1
        ORDER BY start_time NULLS LAST, id ASC
        """

        async with self.get_connection() as conn:
            article_row = await conn.fetchrow(sql_article, article_id)
            if not article_row:
                return None
            events = await conn.fetch(sql_events, article_id)

            metadata = json.loads(article_row.get('metadata')) if article_row.get('metadata') else None
            event_dates = json.loads(article_row.get('event_dates')) if article_row.get('event_dates') else None

            return {
                'id': article_row['id'],
                'title': article_row['title'],
                'content': article_row['content'],
                'summary_text': article_row['summary_text'],
                'url': article_row['url'],
                'source_url': article_row['source_url'],
                'source_file': article_row.get('source_file'),
                'section': article_row.get('section'),
                'page_number': article_row.get('page_number'),
                'date_published': article_row['date_published'].isoformat() if article_row.get('date_published') else None,
                'word_count': article_row.get('word_count'),
                'raw_html': article_row.get('raw_html'),
                'metadata': metadata,
                'location_name': article_row.get('location_name'),
                'location_lat': article_row.get('location_lat'),
                'location_lon': article_row.get('location_lon'),
                'event_dates': event_dates,
                'events': [
                    {
                        'id': ev['id'],
                        'title': ev['title'],
                        'description': ev['description'],
                        'start_time': ev['start_time'].isoformat() if ev['start_time'] else None,
                        'end_time': ev['end_time'].isoformat() if ev['end_time'] else None,
                        'location_name': ev['location_name'],
                        'location_meta': json.loads(ev['location_meta']) if ev['location_meta'] else None,
                    }
                    for ev in events
                ],
            }

    async def get_events(self, days: int = 30) -> List[Dict]:
        sql = """
        SELECT e.id, e.title, e.description, e.start_time, e.end_time,
               e.location_name, e.location_meta, e.article_id, a.title AS article_title
        FROM article_events e
        JOIN articles a ON a.id = e.article_id
        WHERE e.start_time >= $1 OR e.start_time IS NULL
        ORDER BY e.start_time NULLS LAST, e.id ASC
        """

        cutoff = datetime.utcnow() - timedelta(days=days)

        async with self.get_connection() as conn:
            try:
                rows = await conn.fetch(sql, cutoff)
            except exceptions.UndefinedTableError:
                return []

            events: List[Dict] = []
            for row in rows:
                events.append({
                    'id': row['id'],
                    'title': row['title'],
                    'description': row['description'],
                    'start_time': row['start_time'].isoformat() if row['start_time'] else None,
                    'end_time': row['end_time'].isoformat() if row['end_time'] else None,
                    'location_name': row['location_name'],
                    'location_meta': json.loads(row['location_meta']) if row['location_meta'] else None,
                    'article_id': row['article_id'],
                    'article_title': row['article_title'],
                })
            return events
