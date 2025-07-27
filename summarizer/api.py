"""
FastAPI service for AI-powered article summarization.

This module provides REST endpoints for summarizing news articles using OpenAI's API,
with support for batch processing, rate limiting, and token usage tracking.
"""

import logging
import asyncio
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import openai
from openai import AsyncOpenAI

from ..extractor.database import DatabaseManager, StoredArticle
from ..scraper.config import Settings

logger = logging.getLogger(__name__)


# Pydantic models
class ArticleInput(BaseModel):
    """Input model for article summarization."""
    title: str
    content: str
    section: Optional[str] = None
    date_published: Optional[date] = None
    source_url: Optional[str] = None


class SummaryOutput(BaseModel):
    """Output model for article summary."""
    summary: str
    key_points: List[str]
    sentiment: Optional[str] = None
    word_count: int
    confidence_score: float = Field(ge=0.0, le=1.0)
    processing_time_ms: int
    tokens_used: int


class BatchSummaryRequest(BaseModel):
    """Request model for batch summarization."""
    article_ids: List[int]
    force_refresh: bool = False


class BatchSummaryResponse(BaseModel):
    """Response model for batch summarization."""
    total_articles: int
    successful_summaries: int
    failed_summaries: int
    total_tokens_used: int
    processing_time_ms: int
    results: List[Dict[str, Any]]


class SummarizationService:
    """Core service for article summarization using OpenAI API."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.db_manager = DatabaseManager(settings.database_url)
        
        # Prompt templates
        self.system_prompt = """You are a skilled local news summarizer. Your task is to create concise, accurate summaries of local news articles that help busy residents stay informed about their community.

Guidelines:
- Focus on key facts, decisions, and impacts on the local community
- Preserve important names, dates, locations, and numbers
- Highlight any actions residents should take or be aware of
- Maintain a neutral, informative tone
- Keep summaries between 150-250 words"""

        self.user_prompt_template = """Please summarize this local news article:

Title: {title}
Section: {section}
Content: {content}

Provide a JSON response with the following structure:
{{
    "summary": "150-250 word summary focusing on key facts and community impact",
    "key_points": ["3-5 bullet points of most important information"],
    "sentiment": "neutral|positive|negative|mixed",
    "confidence_score": 0.95
}}"""
    
    async def initialize(self):
        """Initialize the service components."""
        await self.db_manager.initialize()
        logger.info("Summarization service initialized")
    
    async def close(self):
        """Close service connections."""
        await self.db_manager.close()
        logger.info("Summarization service closed")
    
    def _count_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough estimate: ~4 characters per token
        return len(text) // 4
    
    def _truncate_content(self, content: str, max_tokens: int = 3000) -> str:
        """Truncate content to fit within token limits."""
        estimated_tokens = self._count_tokens(content)
        if estimated_tokens <= max_tokens:
            return content
        
        # Truncate to approximately max_tokens worth of characters
        max_chars = max_tokens * 4
        truncated = content[:max_chars]
        
        # Try to end at a sentence boundary
        last_period = truncated.rfind('.')
        if last_period > max_chars * 0.8:  # If we find a period in the last 20%
            truncated = truncated[:last_period + 1]
        
        return truncated + "..."
    
    async def summarize_article(self, article: ArticleInput) -> SummaryOutput:
        """
        Summarize a single article using OpenAI API.
        
        Args:
            article: Article input data
            
        Returns:
            Summary output with key points and metadata
        """
        start_time = datetime.utcnow()
        
        try:
            # Prepare content and estimate tokens
            content = self._truncate_content(article.content)
            section = article.section or "General"
            
            user_prompt = self.user_prompt_template.format(
                title=article.title,
                section=section,
                content=content
            )
            
            # Estimate total tokens for the request
            estimated_tokens = (
                self._count_tokens(self.system_prompt) +
                self._count_tokens(user_prompt)
            )
            
            logger.info(f"Summarizing article: {article.title[:50]}... (estimated {estimated_tokens} tokens)")
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=int(self.settings.openai_max_tokens),
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            # Parse JSON response
            import json
            try:
                result_data = json.loads(result_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI JSON response: {e}")
                # Fallback: create a basic summary
                result_data = {
                    "summary": result_text[:500] + "..." if len(result_text) > 500 else result_text,
                    "key_points": ["Summary generated with parsing error"],
                    "sentiment": "neutral",
                    "confidence_score": 0.5
                }
            
            # Calculate processing time
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Create output
            summary_output = SummaryOutput(
                summary=result_data.get("summary", ""),
                key_points=result_data.get("key_points", []),
                sentiment=result_data.get("sentiment"),
                word_count=len(result_data.get("summary", "").split()),
                confidence_score=result_data.get("confidence_score", 0.8),
                processing_time_ms=processing_time_ms,
                tokens_used=tokens_used
            )
            
            logger.info(f"Successfully summarized article: {tokens_used} tokens, {processing_time_ms}ms")
            return summary_output
            
        except Exception as e:
            logger.error(f"Failed to summarize article: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")
    
    async def process_batch_summaries(self, article_ids: List[int], force_refresh: bool = False) -> BatchSummaryResponse:
        """
        Process multiple articles for summarization.
        
        Args:
            article_ids: List of article IDs to summarize
            force_refresh: Whether to re-summarize already processed articles
            
        Returns:
            Batch processing results
        """
        start_time = datetime.utcnow()
        
        results = []
        successful = 0
        failed = 0
        total_tokens = 0
        
        logger.info(f"Starting batch summarization of {len(article_ids)} articles")
        
        for article_id in article_ids:
            try:
                # Get article from database
                articles = await self.db_manager.get_articles_for_processing('extracted', 1, article_id)
                if not articles:
                    results.append({
                        "article_id": article_id,
                        "status": "failed",
                        "error": "Article not found"
                    })
                    failed += 1
                    continue
                
                article = articles[0]
                
                # Check if already summarized (unless force refresh)
                if not force_refresh and article.processing_status == 'summarized':
                    results.append({
                        "article_id": article_id,
                        "status": "skipped",
                        "reason": "Already summarized"
                    })
                    continue
                
                # Create article input
                article_input = ArticleInput(
                    title=article.title,
                    content=article.content,
                    section=article.section,
                    date_published=article.date_published,
                    source_url=article.source_url
                )
                
                # Summarize
                summary = await self.summarize_article(article_input)
                
                # Store summary in database
                await self.db_manager.store_summary(
                    article_id=article_id,
                    summary=summary.summary,
                    key_points=summary.key_points,
                    sentiment=summary.sentiment,
                    confidence_score=summary.confidence_score,
                    tokens_used=summary.tokens_used
                )
                
                # Mark article as summarized
                await self.db_manager.update_processing_status(article_id, 'summarized')
                
                results.append({
                    "article_id": article_id,
                    "status": "success",
                    "summary": summary.summary,
                    "tokens_used": summary.tokens_used,
                    "processing_time_ms": summary.processing_time_ms
                })
                
                successful += 1
                total_tokens += summary.tokens_used
                
                # Rate limiting: small delay between requests
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to process article {article_id}: {str(e)}")
                results.append({
                    "article_id": article_id,
                    "status": "failed",
                    "error": str(e)
                })
                failed += 1
        
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        logger.info(f"Batch summarization complete: {successful} successful, {failed} failed, {total_tokens} tokens")
        
        return BatchSummaryResponse(
            total_articles=len(article_ids),
            successful_summaries=successful,
            failed_summaries=failed,
            total_tokens_used=total_tokens,
            processing_time_ms=processing_time_ms,
            results=results
        )


# Global service instance
_service: Optional[SummarizationService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global _service
    
    # Startup
    settings = Settings()
    _service = SummarizationService(settings)
    await _service.initialize()
    logger.info("Summarization API started")
    
    yield
    
    # Shutdown
    if _service:
        await _service.close()
    logger.info("Summarization API stopped")


# FastAPI app
app = FastAPI(
    title="News Analyzer - Summarization Service",
    description="AI-powered summarization service for local news articles",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_service() -> SummarizationService:
    """Dependency to get the service instance."""
    if _service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return _service


# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/summarize", response_model=SummaryOutput)
async def summarize_single_article(
    article: ArticleInput,
    service: SummarizationService = Depends(get_service)
):
    """Summarize a single article."""
    return await service.summarize_article(article)


@app.post("/summarize/batch", response_model=BatchSummaryResponse)
async def summarize_batch_articles(
    request: BatchSummaryRequest,
    background_tasks: BackgroundTasks,
    service: SummarizationService = Depends(get_service)
):
    """Process multiple articles for summarization."""
    return await service.process_batch_summaries(
        request.article_ids,
        request.force_refresh
    )


@app.get("/articles/pending")
async def get_pending_articles(
    limit: int = 50,
    service: SummarizationService = Depends(get_service)
):
    """Get articles pending summarization."""
    articles = await service.db_manager.get_articles_for_processing('extracted', limit)
    return {
        "count": len(articles),
        "articles": [
            {
                "id": article.id,
                "title": article.title,
                "section": article.section,
                "date_published": article.date_published.isoformat() if article.date_published else None,
                "word_count": len(article.content.split()),
                "processing_status": article.processing_status
            }
            for article in articles
        ]
    }


@app.get("/stats")
async def get_summarization_stats(
    days: int = 7,
    service: SummarizationService = Depends(get_service)
):
    """Get summarization statistics."""
    stats = await service.db_manager.get_processing_stats(days)
    return {
        "period_days": days,
        "summary": stats.get("summary", {}),
        "daily_stats": stats.get("daily_stats", [])
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")