"""
Ntfy notification service for automated news digest delivery.

This module provides push notifications to iPhone/Android via ntfy,
a free and self-hosted notification service.
"""

import logging
import asyncio
from datetime import datetime, date
from typing import List, Dict, Optional, Any
import aiohttp
import json
from base64 import b64encode

from ..extractor.database import DatabaseManager, StoredArticle
from ..scraper.config import Settings

logger = logging.getLogger(__name__)


class NtfyNotifier:
    """Handles push notifications via ntfy."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ntfy_url = settings.ntfy_url or "http://ntfy-service.news-analyzer.svc.cluster.local"
        self.ntfy_topic = settings.ntfy_topic or "news-digest"
        self.ntfy_token = settings.ntfy_token  # Optional auth token
        
    async def send_digest_notification(self, articles: List[StoredArticle], summaries: Dict[int, Dict]) -> bool:
        """
        Send digest notification via ntfy.
        
        Args:
            articles: List of articles to include
            summaries: Dictionary mapping article IDs to summary data
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # Prepare notification
            notification = self._prepare_notification(articles, summaries)
            
            # Send to ntfy
            headers = {
                "Content-Type": "application/json",
            }
            
            if self.ntfy_token:
                headers["Authorization"] = f"Bearer {self.ntfy_token}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ntfy_url}/{self.ntfy_topic}",
                    json=notification,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info("Ntfy notification sent successfully")
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"Failed to send ntfy notification: {response.status} - {text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending ntfy notification: {str(e)}")
            return False
    
    def _prepare_notification(self, articles: List[StoredArticle], summaries: Dict[int, Dict]) -> Dict:
        """Prepare ntfy notification payload."""
        # Get article count and top stories
        article_count = len(articles)
        top_articles = articles[:3]  # Top 3 for the notification
        
        # Build title
        title = f"📰 SW Virginia News - {article_count} new articles"
        
        # Build message body
        message_parts = []
        
        for article in top_articles:
            summary_data = summaries.get(article.id, {})
            summary_text = summary_data.get('summary_text', article.content[:100] + '...')
            
            # Clean summary for notification
            if "Key Points:" in summary_text:
                summary_text = summary_text.split("Key Points:")[0].strip()
            
            # Truncate to 200 chars for notification
            if len(summary_text) > 200:
                summary_text = summary_text[:197] + "..."
            
            section = f"[{article.section}]" if article.section else ""
            message_parts.append(f"• {section} {article.title}\n  {summary_text}")
        
        if article_count > 3:
            message_parts.append(f"\n... and {article_count - 3} more articles")
        
        message = "\n\n".join(message_parts)
        
        # Build notification with actions
        notification = {
            "topic": self.ntfy_topic,
            "title": title,
            "message": message,
            "priority": 3,  # Default priority
            "tags": ["newspaper", "news"],
            "click": "https://swvatoday.com/eedition/",  # Click action
            "actions": [
                {
                    "action": "view",
                    "label": "Read Digest",
                    "url": "https://swvatoday.com/eedition/"
                }
            ],
            "attach": None,  # Could attach full digest as file
            "filename": None
        }
        
        # Add full digest as attachment if configured
        if hasattr(self.settings, 'ntfy_attach_full') and self.settings.ntfy_attach_full:
            full_digest = self._create_text_digest(articles, summaries)
            notification["attach"] = f"data:text/plain;base64,{b64encode(full_digest.encode()).decode()}"
            notification["filename"] = f"news-digest-{date.today().isoformat()}.txt"
        
        return notification
    
    def _create_text_digest(self, articles: List[StoredArticle], summaries: Dict[int, Dict]) -> str:
        """Create full text digest for attachment."""
        text = f"""SW VIRGINIA NEWS DIGEST
{date.today().strftime('%B %d, %Y')} • {len(articles)} Articles

"""
        # Group by section
        sections = {}
        for article in articles:
            section = article.section or "General"
            if section not in sections:
                sections[section] = []
            sections[section].append(article)
        
        for section_name, section_articles in sections.items():
            text += f"\n{section_name.upper()}\n{'=' * len(section_name)}\n\n"
            
            for article in section_articles:
                summary_data = summaries.get(article.id, {})
                summary_text = summary_data.get('summary_text', article.content[:300] + '...')
                
                text += f"{article.title}\n"
                text += f"{summary_text}\n"
                
                if article.url or article.source_url:
                    text += f"\nRead more: {article.url or article.source_url}\n"
                
                text += "\n" + "-" * 50 + "\n\n"
        
        text += f"\nGenerated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        text += "This is an automated digest from SW Virginia Today's e-edition.\n"
        
        return text


class UpdatedNotificationService:
    """Updated notification service with ntfy support."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_manager = DatabaseManager(settings.database_url)
        
        # Initialize notifiers
        self.email_notifier = None  # Removed SendGrid
        self.ntfy_notifier = NtfyNotifier(settings)
        self.slack_notifier = None  # Keep if still wanted
        
        if hasattr(settings, 'slack_webhook_url') and settings.slack_webhook_url:
            from .service import SlackNotifier
            self.slack_notifier = SlackNotifier(settings.slack_webhook_url)
    
    async def initialize(self):
        """Initialize the notification service."""
        await self.db_manager.initialize()
        logger.info("Notification service initialized")
    
    async def close(self):
        """Close the notification service."""
        await self.db_manager.close()
        logger.info("Notification service closed")
    
    async def send_daily_digest(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Send daily digest for articles from specified date.
        
        Args:
            target_date: Date to send digest for (defaults to today)
            
        Returns:
            Dictionary with results of notification delivery
        """
        if target_date is None:
            target_date = date.today()
        
        logger.info(f"Preparing daily digest for {target_date}")
        
        try:
            # Get summarized articles from the target date
            articles = await self._get_articles_for_digest(target_date)
            
            if not articles:
                logger.info(f"No articles found for {target_date}")
                return {
                    'date': target_date.isoformat(),
                    'articles_count': 0,
                    'ntfy_sent': False,
                    'slack_sent': False,
                    'message': 'No articles to send'
                }
            
            # Get summaries for the articles
            summaries = await self._get_summaries_for_articles([a.id for a in articles])
            
            results = {
                'date': target_date.isoformat(),
                'articles_count': len(articles),
                'ntfy_sent': False,
                'slack_sent': False,
                'errors': []
            }
            
            # Send ntfy notification
            try:
                ntfy_success = await self.ntfy_notifier.send_digest_notification(articles, summaries)
                results['ntfy_sent'] = ntfy_success
                if ntfy_success:
                    logger.info("Ntfy notification sent successfully")
            except Exception as e:
                logger.error(f"Ntfy notification failed: {str(e)}")
                results['errors'].append(f"Ntfy failed: {str(e)}")
            
            # Send Slack notification if configured
            if self.slack_notifier:
                try:
                    slack_success = await self.slack_notifier.send_digest_notification(articles, summaries)
                    results['slack_sent'] = slack_success
                    if slack_success:
                        logger.info("Slack notification sent successfully")
                except Exception as e:
                    logger.error(f"Slack notification failed: {str(e)}")
                    results['errors'].append(f"Slack failed: {str(e)}")
            
            # Mark articles as notified
            if results['ntfy_sent'] or results['slack_sent']:
                await self._mark_articles_notified([a.id for a in articles])
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to send daily digest: {str(e)}")
            return {
                'date': target_date.isoformat(),
                'articles_count': 0,
                'ntfy_sent': False,
                'slack_sent': False,
                'error': str(e)
            }
    
    async def _get_articles_for_digest(self, target_date: date) -> List[StoredArticle]:
        """Get articles that are ready for digest delivery."""
        # Get articles that were extracted/summarized for the target date
        sql = """
        SELECT * FROM articles 
        WHERE DATE(date_extracted) = $1 
        AND processing_status IN ('summarized', 'extracted')
        ORDER BY date_published DESC, date_extracted DESC
        LIMIT 50
        """
        
        async with self.db_manager.get_connection() as conn:
            rows = await conn.fetch(sql, target_date)
            
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
    
    async def _get_summaries_for_articles(self, article_ids: List[int]) -> Dict[int, Dict]:
        """Get summaries for the given article IDs."""
        if not article_ids:
            return {}
        
        sql = """
        SELECT article_id, summary_text, summary_type, model_used, tokens_used
        FROM summaries 
        WHERE article_id = ANY($1)
        """
        
        summaries = {}
        async with self.db_manager.get_connection() as conn:
            rows = await conn.fetch(sql, article_ids)
            
            for row in rows:
                summaries[row['article_id']] = {
                    'summary_text': row['summary_text'],
                    'summary_type': row['summary_type'],
                    'model_used': row['model_used'],
                    'tokens_used': row['tokens_used']
                }
        
        return summaries
    
    async def _mark_articles_notified(self, article_ids: List[int]):
        """Mark articles as notified."""
        if not article_ids:
            return
        
        sql = "UPDATE articles SET processing_status = 'notified' WHERE id = ANY($1)"
        
        async with self.db_manager.get_connection() as conn:
            await conn.execute(sql, article_ids)
        
        logger.info(f"Marked {len(article_ids)} articles as notified")