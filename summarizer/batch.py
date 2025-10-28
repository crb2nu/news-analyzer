#!/usr/bin/env python3
"""
Batch processing script for summarizing articles.

This module fetches pending articles from the database, processes them
in batches for summarization using OpenAI, and updates their status.
Designed to be run as a CronJob in Kubernetes.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import time
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from existing modules
try:
    from summarizer.database import DatabaseManager, StoredArticle
    from summarizer.config import Settings
except Exception:
    from database import DatabaseManager, StoredArticle
    from config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SummaryResponse(BaseModel):
    """Model for summary response."""
    summary: str = Field(..., description="Concise summary of the article")
    key_points: List[str] = Field(..., description="Key points from the article")
    sentiment: str = Field(..., description="Overall sentiment: positive, negative, or neutral")
    topics: List[str] = Field(..., description="Main topics covered in the article")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)


class ArticleSummarizer:
    """Handles article summarization using OpenAI API."""
    
    def __init__(self, settings: Settings):
        """Initialize the summarizer with OpenAI client."""
        self.settings = settings
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_tokens = int(settings.openai_max_tokens)
        
        # System prompt for local news summarization
        self.system_prompt = """You are a skilled local news summarizer. Your task is to create concise, accurate summaries of local news articles that help busy residents stay informed about their community.

Guidelines:
- Focus on key facts, decisions, and impacts on the local community
- Preserve important names, dates, locations, and numbers
- Highlight any actions residents should take or be aware of
- Maintain a neutral, informative tone
- Keep summaries between 150-250 words
- Extract 3-5 key points
- Identify the overall sentiment
- List 2-4 main topics covered"""
        
        logger.info(f"Initialized ArticleSummarizer with model: {self.model}")
    
    def _truncate_content(self, content: str, max_chars: int = 6000) -> str:
        """Truncate content to manage token limits."""
        if len(content) <= max_chars:
            return content
        
        truncated = content[:max_chars]
        # Try to end at a sentence boundary
        last_period = truncated.rfind('.')
        if last_period > max_chars * 0.8:
            truncated = truncated[:last_period + 1]
        
        return truncated + "..."
    
    async def summarize_article(self, article: StoredArticle) -> Optional[SummaryResponse]:
        """
        Summarize a single article using OpenAI API.
        
        Args:
            article: Article to summarize
            
        Returns:
            SummaryResponse or None if failed
        """
        try:
            # Prepare content
            content = self._truncate_content(article.content)
            
            # Create the prompt
            user_prompt = f"""Please summarize this local news article:

Title: {article.title}
Section: {article.section or 'General'}
Published: {article.date_published.strftime('%Y-%m-%d') if article.date_published else 'Unknown'}

Article Content:
{content}

Provide a JSON response with the following structure:
{{
    "summary": "150-250 word summary focusing on key facts and community impact",
    "key_points": ["3-5 bullet points of most important information"],
    "sentiment": "neutral|positive|negative|mixed",
    "topics": ["2-4 main topics covered"],
    "confidence_score": 0.95
}}"""

            # Make API call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=self.max_tokens
            )
            
            # Parse response
            content = response.choices[0].message.content
            result_data = json.loads(content)
            
            return SummaryResponse(
                summary=result_data.get("summary", ""),
                key_points=result_data.get("key_points", []),
                sentiment=result_data.get("sentiment", "neutral"),
                topics=result_data.get("topics", []),
                confidence_score=result_data.get("confidence_score", 0.8)
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response for article {article.id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error summarizing article {article.id}: {str(e)}")
            return None


class BatchProcessor:
    """Handles batch processing of articles for summarization."""
    
    def __init__(self, settings: Settings):
        """Initialize the batch processor."""
        self.settings = settings
        self.summarizer = ArticleSummarizer(settings)
        self.db_manager = DatabaseManager(settings.database_url)
        self.batch_size = int(os.getenv("SUMMARIZER_BATCH_SIZE", "10"))
        self.max_retries = int(os.getenv("SUMMARIZER_MAX_RETRIES", "3"))
        
    async def initialize(self):
        """Initialize database connection."""
        await self.db_manager.initialize()
        logger.info("Batch processor initialized")
    
    async def close(self):
        """Close database connection."""
        await self.db_manager.close()
        logger.info("Batch processor closed")
    
    async def process_article(self, article: StoredArticle) -> Dict[str, Any]:
        """
        Process a single article for summarization.
        
        Args:
            article: Article to process
            
        Returns:
            Processing result dictionary
        """
        start_time = time.time()
        
        try:
            # Summarize the article
            summary_response = await self.summarizer.summarize_article(article)
            
            if summary_response:
                # Calculate processing time
                processing_time_ms = int((time.time() - start_time) * 1000)
                
                # Store summary in database
                summary_id = await self.db_manager.store_summary(
                    article_id=article.id,
                    summary=summary_response.summary,
                    key_points=summary_response.key_points,
                    sentiment=summary_response.sentiment,
                    confidence_score=summary_response.confidence_score,
                    tokens_used=0,  # Would need token counting implementation
                    processing_time_ms=processing_time_ms,
                    model_used=self.summarizer.model
                )
                
                # Update article status
                await self.db_manager.update_processing_status(article.id, 'summarized')
                
                logger.info(f"Successfully summarized article {article.id}: '{article.title[:50]}...'")
                
                return {
                    "article_id": article.id,
                    "status": "success",
                    "summary_id": summary_id,
                    "processing_time_ms": processing_time_ms
                }
            else:
                # Failed summarization
                logger.warning(f"Failed to summarize article {article.id}")
                return {
                    "article_id": article.id,
                    "status": "failed",
                    "error": "Summarization returned no result"
                }
                
        except Exception as e:
            logger.error(f"Exception processing article {article.id}: {str(e)}")
            return {
                "article_id": article.id,
                "status": "error",
                "error": str(e)
            }
    
    async def process_batch(self, articles: List[StoredArticle]) -> Dict[str, int]:
        """
        Process a batch of articles for summarization.
        
        Args:
            articles: List of articles to process
            
        Returns:
            Dictionary with processing statistics
        """
        stats = {"success": 0, "failed": 0, "error": 0, "total": len(articles)}
        
        logger.info(f"Processing batch of {len(articles)} articles")
        
        # Process articles concurrently
        tasks = [self.process_article(article) for article in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        for result in results:
            if isinstance(result, Exception):
                stats["error"] += 1
                logger.error(f"Task exception: {str(result)}")
            elif isinstance(result, dict):
                if result["status"] == "success":
                    stats["success"] += 1
                elif result["status"] == "failed":
                    stats["failed"] += 1
                else:
                    stats["error"] += 1
            else:
                stats["error"] += 1
        
        logger.info(
            f"Batch completed: {stats['success']} successful, "
            f"{stats['failed']} failed, {stats['error']} errors"
        )
        
        return stats
    
    async def run(self, max_batches: int = 10) -> Dict[str, Any]:
        """
        Run the batch processor.
        
        Args:
            max_batches: Maximum number of batches to process
            
        Returns:
            Overall processing statistics
        """
        overall_stats = {
            "batches_processed": 0,
            "total_articles": 0,
            "successful": 0,
            "failed": 0,
            "errors": 0,
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None
        }
        
        try:
            await self.initialize()
            
            for batch_num in range(max_batches):
                # Get pending articles
                articles = await self.db_manager.get_articles_for_processing(
                    processing_status='extracted',
                    limit=self.batch_size
                )
                
                if not articles:
                    logger.info("No more pending articles to process")
                    break
                
                logger.info(f"Starting batch {batch_num + 1}/{max_batches} with {len(articles)} articles")
                
                # Process the batch
                batch_stats = await self.process_batch(articles)
                
                # Update overall statistics
                overall_stats["batches_processed"] += 1
                overall_stats["total_articles"] += batch_stats["total"]
                overall_stats["successful"] += batch_stats["success"]
                overall_stats["failed"] += batch_stats["failed"]
                overall_stats["errors"] += batch_stats["error"]
                
                # Rate limiting: small delay between batches
                if batch_num < max_batches - 1:
                    await asyncio.sleep(1)
            
            overall_stats["end_time"] = datetime.utcnow().isoformat()
            
            logger.info(
                f"Batch processing completed: "
                f"{overall_stats['batches_processed']} batches, "
                f"{overall_stats['successful']} successful, "
                f"{overall_stats['failed']} failed, "
                f"{overall_stats['errors']} errors"
            )
            
            return overall_stats
            
        except Exception as e:
            logger.error(f"Critical error in batch processor: {str(e)}")
            overall_stats["error"] = str(e)
            overall_stats["end_time"] = datetime.utcnow().isoformat()
            return overall_stats
        finally:
            await self.close()


async def main():
    """Main entry point for the batch processor."""
    logger.info("Starting summarizer batch processor")
    
    try:
        # Load settings
        settings = Settings()
        
        # Check for required configuration
        if not settings.openai_api_key:
            logger.error("OPENAI_API_KEY is not configured")
            sys.exit(1)
        
        # Get batch configuration
        max_batches = int(os.getenv("SUMMARIZER_MAX_BATCHES", "10"))
        
        # Run batch processor
        processor = BatchProcessor(settings)
        stats = await processor.run(max_batches=max_batches)
        
        # Log final statistics
        logger.info(f"Final statistics: {json.dumps(stats, indent=2)}")
        
        # Exit with appropriate code
        if stats.get("error"):
            sys.exit(1)
        elif stats["errors"] > 0 or (stats["failed"] > 0 and stats["successful"] == 0):
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
