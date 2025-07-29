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
from datetime import datetime, date
import json

import asyncpg
from asyncpg import Pool, Connection
from contextlib import asynccontextmanager

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