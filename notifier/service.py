"""
Notification service for automated news digest delivery.

This module provides email and Slack notification capabilities with support for:
- Daily digest emails with HTML formatting
- Slack webhook notifications
- Template-based message generation
- Subscription management and filtering
"""

import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import aiohttp
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from ..extractor.database import DatabaseManager, StoredArticle
from ..scraper.config import Settings

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Handles email notifications via SendGrid."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sendgrid_client = SendGridAPIClient(api_key=settings.email_api_key)
        
        # Initialize Jinja2 environment for templates
        template_dir = Path(__file__).parent / "templates"
        template_dir.mkdir(exist_ok=True)
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    async def send_daily_digest(self, articles: List[StoredArticle], summaries: Dict[int, Dict]) -> bool:
        """
        Send daily digest email with articles and summaries.
        
        Args:
            articles: List of articles to include
            summaries: Dictionary mapping article IDs to summary data
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Prepare email data
            email_data = self._prepare_digest_data(articles, summaries)
            
            # Render HTML template
            html_content = self._render_html_template(email_data)
            
            # Create email
            from_email = Email(self.settings.email_from, "SW Virginia News Digest")
            to_email = To(self.settings.email_to)
            subject = f"SW Virginia News Digest - {email_data['date'].strftime('%B %d, %Y')}"
            
            # Create plain text version
            text_content = self._create_text_version(email_data)
            
            mail = Mail(
                from_email=from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content,
                plain_text_content=text_content
            )
            
            # Send email
            response = self.sendgrid_client.send(mail)
            
            if response.status_code == 202:
                logger.info(f"Daily digest email sent successfully to {self.settings.email_to}")
                return True
            else:
                logger.error(f"Failed to send email: {response.status_code} - {response.body}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending daily digest email: {str(e)}")
            return False
    
    def _prepare_digest_data(self, articles: List[StoredArticle], summaries: Dict[int, Dict]) -> Dict:
        """Prepare data structure for email template."""
        # Group articles by section
        sections = {}
        total_articles = len(articles)
        
        for article in articles:
            section = article.section or "General"
            if section not in sections:
                sections[section] = []
            
            # Get summary for this article
            summary_data = summaries.get(article.id, {})
            
            article_data = {
                'id': article.id,
                'title': article.title,
                'summary': summary_data.get('summary_text', article.content[:200] + '...'),
                'key_points': self._extract_key_points(summary_data.get('summary_text', '')),
                'url': article.url or article.source_url,
                'author': article.author,
                'date_published': article.date_published,
                'word_count': article.word_count,
                'section': section
            }
            
            sections[section].append(article_data)
        
        # Sort sections by priority
        section_priority = {
            'Local': 1, 'News': 2, 'Sports': 3, 'Business': 4, 
            'Opinion': 5, 'Obituaries': 6, 'General': 7
        }
        
        sorted_sections = sorted(
            sections.items(), 
            key=lambda x: section_priority.get(x[0], 99)
        )
        
        return {
            'date': date.today(),
            'total_articles': total_articles,
            'sections': sorted_sections,
            'generated_at': datetime.now()
        }
    
    def _extract_key_points(self, summary_text: str) -> List[str]:
        """Extract key points from summary text."""
        if not summary_text:
            return []
        
        # Look for key points section
        if "Key Points:" in summary_text:
            points_section = summary_text.split("Key Points:")[1]
            if "Sentiment:" in points_section:
                points_section = points_section.split("Sentiment:")[0]
            
            points = []
            for line in points_section.split('\n'):
                line = line.strip()
                if line.startswith('•') or line.startswith('-'):
                    points.append(line[1:].strip())
            
            return points[:3]  # Limit to top 3 points
        
        return []
    
    def _render_html_template(self, data: Dict) -> str:
        """Render HTML email template."""
        try:
            template = self.jinja_env.get_template('daily_digest.html')
            return template.render(**data)
        except Exception:
            # Fallback to basic HTML if template doesn't exist
            return self._create_basic_html(data)
    
    def _create_basic_html(self, data: Dict) -> str:
        """Create basic HTML email if template is not available."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>SW Virginia News Digest</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }}
                .header {{ background-color: #2c5aa0; color: white; padding: 20px; text-align: center; }}
                .section {{ margin: 20px 0; border-bottom: 1px solid #eee; }}
                .article {{ margin: 15px 0; padding: 10px; border-left: 3px solid #2c5aa0; }}
                .article-title {{ font-weight: bold; font-size: 16px; margin-bottom: 5px; }}
                .article-summary {{ margin: 10px 0; }}
                .key-points {{ margin: 10px 0; }}
                .key-points li {{ margin: 5px 0; }}
                .footer {{ margin-top: 30px; padding: 20px; background-color: #f5f5f5; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>SW Virginia News Digest</h1>
                <p>{data['date'].strftime('%B %d, %Y')} • {data['total_articles']} Articles</p>
            </div>
        """
        
        for section_name, articles in data['sections']:
            html += f"""
            <div class="section">
                <h2>{section_name}</h2>
            """
            
            for article in articles:
                html += f"""
                <div class="article">
                    <div class="article-title">{article['title']}</div>
                    <div class="article-summary">{article['summary']}</div>
                """
                
                if article['key_points']:
                    html += "<div class='key-points'><strong>Key Points:</strong><ul>"
                    for point in article['key_points']:
                        html += f"<li>{point}</li>"
                    html += "</ul></div>"
                
                if article['url']:
                    html += f"<p><a href='{article['url']}'>Read full article</a></p>"
                
                html += "</div>"
            
            html += "</div>"
        
        html += f"""
            <div class="footer">
                <p>Generated on {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>This is an automated digest from SW Virginia Today's e-edition.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _create_text_version(self, data: Dict) -> str:
        """Create plain text version of the email."""
        text = f"""
SW VIRGINIA NEWS DIGEST
{data['date'].strftime('%B %d, %Y')} • {data['total_articles']} Articles

"""
        
        for section_name, articles in data['sections']:
            text += f"\n{section_name.upper()}\n{'=' * len(section_name)}\n\n"
            
            for article in articles:
                text += f"{article['title']}\n"
                text += f"{article['summary']}\n"
                
                if article['key_points']:
                    text += "\nKey Points:\n"
                    for point in article['key_points']:
                        text += f"• {point}\n"
                
                if article['url']:
                    text += f"\nRead more: {article['url']}\n"
                
                text += "\n" + "-" * 50 + "\n\n"
        
        text += f"\nGenerated on {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        text += "This is an automated digest from SW Virginia Today's e-edition.\n"
        
        return text


class SlackNotifier:
    """Handles Slack webhook notifications."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send_digest_notification(self, articles: List[StoredArticle], summaries: Dict[int, Dict]) -> bool:
        """
        Send digest notification to Slack.
        
        Args:
            articles: List of articles to include
            summaries: Dictionary mapping article IDs to summary data
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # Prepare Slack message
            message = self._prepare_slack_message(articles, summaries)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=message) as response:
                    if response.status == 200:
                        logger.info("Slack notification sent successfully")
                        return True
                    else:
                        logger.error(f"Failed to send Slack notification: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Slack notification: {str(e)}")
            return False
    
    def _prepare_slack_message(self, articles: List[StoredArticle], summaries: Dict[int, Dict]) -> Dict:
        """Prepare Slack message payload."""
        # Get top articles (limit to 5 for Slack)
        top_articles = articles[:5]
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📰 SW Virginia News Digest - {date.today().strftime('%B %d, %Y')}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*{len(articles)} new articles* • Generated at {datetime.now().strftime('%I:%M %p')}"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
        
        for article in top_articles:
            summary_data = summaries.get(article.id, {})
            summary_text = summary_data.get('summary_text', article.content[:150] + '...')
            
            # Clean summary for Slack (remove key points section)
            if "Key Points:" in summary_text:
                summary_text = summary_text.split("Key Points:")[0].strip()
            
            article_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{article.title}*\n{summary_text}"
                }
            }
            
            if article.url or article.source_url:
                article_block["accessory"] = {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Read More"
                    },
                    "url": article.url or article.source_url
                }
            
            blocks.append(article_block)
            
            if article != top_articles[-1]:  # Add divider except for last article
                blocks.append({"type": "divider"})
        
        if len(articles) > 5:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_... and {len(articles) - 5} more articles in today's digest_"
                    }
                ]
            })
        
        return {
            "blocks": blocks,
            "username": "News Analyzer",
            "icon_emoji": ":newspaper:"
        }


class NotificationService:
    """Main notification service coordinating email and Slack delivery."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db_manager = DatabaseManager(settings.database_url)
        
        # Initialize notifiers
        self.email_notifier = EmailNotifier(settings) if settings.email_api_key else None
        self.slack_notifier = SlackNotifier(settings.slack_webhook_url) if hasattr(settings, 'slack_webhook_url') and settings.slack_webhook_url else None
        
        if not self.email_notifier and not self.slack_notifier:
            logger.warning("No notification channels configured")
    
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
                    'email_sent': False,
                    'slack_sent': False,
                    'message': 'No articles to send'
                }
            
            # Get summaries for the articles
            summaries = await self._get_summaries_for_articles([a.id for a in articles])
            
            results = {
                'date': target_date.isoformat(),
                'articles_count': len(articles),
                'email_sent': False,
                'slack_sent': False,
                'errors': []
            }
            
            # Send email digest
            if self.email_notifier:
                try:
                    email_success = await self.email_notifier.send_daily_digest(articles, summaries)
                    results['email_sent'] = email_success
                    if email_success:
                        logger.info("Email digest sent successfully")
                except Exception as e:
                    logger.error(f"Email digest failed: {str(e)}")
                    results['errors'].append(f"Email failed: {str(e)}")
            
            # Send Slack notification
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
            if results['email_sent'] or results['slack_sent']:
                await self._mark_articles_notified([a.id for a in articles])
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to send daily digest: {str(e)}")
            return {
                'date': target_date.isoformat(),
                'articles_count': 0,
                'email_sent': False,
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


async def main():
    """CLI interface for notification service."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Send news notifications")
    parser.add_argument("--date", type=str, help="Date to send digest for (YYYY-MM-DD)")
    parser.add_argument("--email-only", action="store_true", help="Send email only")
    parser.add_argument("--slack-only", action="store_true", help="Send Slack only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Parse date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            exit(1)
    else:
        target_date = date.today()
    
    # Initialize notification service
    settings = Settings()
    service = NotificationService(settings)
    
    try:
        await service.initialize()
        
        # Override notifiers based on args
        if args.email_only:
            service.slack_notifier = None
        elif args.slack_only:
            service.email_notifier = None
        
        # Send digest
        results = await service.send_daily_digest(target_date)
        
        print(f"Daily Digest Results for {target_date}:")
        print(f"  Articles: {results['articles_count']}")
        print(f"  Email sent: {results['email_sent']}")
        print(f"  Slack sent: {results['slack_sent']}")
        
        if results.get('errors'):
            print("\nErrors:")
            for error in results['errors']:
                print(f"  {error}")
        
        if results.get('error'):
            print(f"\nFatal error: {results['error']}")
            exit(1)
    
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())