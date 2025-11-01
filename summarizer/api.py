"""
FastAPI service for AI-powered article summarization.

This module provides REST endpoints for summarizing news articles using OpenAI's API,
with support for batch processing, rate limiting, and token usage tracking.
"""

import logging
import asyncio
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import openai
from openai import AsyncOpenAI
from minio import Minio
from minio.error import S3Error
import html

try:
    # When running as a package (e.g., python -m summarizer.api)
    from .database import DatabaseManager, StoredArticle
    from .config import Settings
    from .utils import extract_json_object
except Exception:
    # When running as a module from the folder (e.g., python -m api)
    from database import DatabaseManager, StoredArticle
    from config import Settings
    from utils import extract_json_object

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
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_api_base:
            client_kwargs["base_url"] = settings.openai_api_base.rstrip("/")
        self.client = AsyncOpenAI(**client_kwargs)
        self.db_manager = DatabaseManager(settings.database_url)
        self.minio_bucket = settings.minio_bucket
        self.minio_client = None
        if settings.minio_endpoint and settings.minio_access_key:
            endpoint = settings.minio_endpoint
            secure = False
            if endpoint.startswith("https://"):
                secure = True
                endpoint = endpoint[len("https://") :]
            elif endpoint.startswith("http://"):
                endpoint = endpoint[len("http://") :]
            self.minio_client = Minio(
                endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=secure,
            )
        
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
            result_text = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens

            result_data, used_fallback = extract_json_object(result_text)
            if used_fallback:
                logger.warning("Using fallback parser for summarization response")
            
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


def build_source_page(article: Dict) -> str:
    title = html.escape(article.get('title') or 'Article')
    section = article.get('section') or 'General'
    location = article.get('location_name')
    published = article.get('date_published')
    events = article.get('events') or []
    summary = article.get('summary_text')

    raw_html = article.get('raw_html')
    if raw_html:
        body_html = raw_html
    else:
        content = html.escape(article.get('content', ''))
        body_html = f"<pre class=\"article-content\">{content}</pre>"

    events_html = ""
    if events:
        lines = []
        for ev in events:
            line = "<li><strong>{}</strong>".format(html.escape(ev.get('title', 'Event')))
            if ev.get('start_time'):
                line += f"<span class=\"event-time\">{html.escape(ev['start_time'])}</span>"
            if ev.get('location_name'):
                line += f"<span class=\"event-location\">{html.escape(ev['location_name'])}</span>"
            if ev.get('description'):
                line += f"<p>{html.escape(ev['description'])}</p>"
            line += "</li>"
            lines.append(line)
        events_html = """
        <section class="events">
          <h2>Related Events</h2>
          <ul>
            {}
          </ul>
        </section>
        """.format("\n".join(lines))

    summary_html = ""
    if summary:
        paragraphs = [html.escape(p.strip()) for p in summary.split("\n\n") if p.strip()]
        summary_html = "<section class=\"summary\"><h2>Summary</h2>" + "".join(
            f"<p>{para}</p>" for para in paragraphs
        ) + "</section>"

    meta_chips = [f"<span class=\"meta-tag\">{html.escape(section)}</span>"]
    if location:
        meta_chips.append(f"<span class=\"meta-tag\">{html.escape(location)}</span>")
    if published:
        meta_chips.append(f"<span class=\"meta-tag\">Published {html.escape(published)}</span>")
    metadata_html = "".join(meta_chips)

    template = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title} — Original Source</title>
  <style>
    body {{ font-family: 'Inter', system-ui, sans-serif; margin: 0; background:#0f172a; color:#e5e7eb; }}
    .container {{ max-width: 920px; margin: 0 auto; padding: 32px 20px 56px; }}
    a {{ color: #38bdf8; }}
    header {{ margin-bottom: 24px; }}
    h1 {{ margin: 0 0 12px; font-size: 2.2rem; line-height: 1.2; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:8px; color:#94a3b8; font-size:0.9rem; margin-bottom: 20px; }}
    .meta-tag {{ background:rgba(148,163,184,0.15); padding:4px 10px; border-radius:999px; }}
    .summary {{ background:rgba(56,189,248,0.1); border:1px solid rgba(56,189,248,0.25); padding:16px 20px; border-radius:12px; margin-bottom:24px; }}
    .summary h2 {{ margin-top:0; }}
    .article-body {{ background:rgba(15,23,42,0.9); border:1px solid rgba(148,163,184,0.2); border-radius:16px; padding:24px; box-shadow:0 25px 50px -12px rgba(15,23,42,0.6); }}
    .article-content {{ white-space:pre-wrap; line-height:1.6; font-size:1rem; color:#e2e8f0; }}
    .events {{ margin-top:32px; }}
    .events ul {{ list-style:none; padding:0; margin:0; display:grid; gap:16px; }}
    .events li {{ background:rgba(59,130,246,0.12); border:1px solid rgba(59,130,246,0.25); padding:16px 20px; border-radius:12px; }}
    .events .event-time, .events .event-location {{ display:inline-block; margin-left:10px; color:#cbd5f5; font-size:0.9rem; }}
    footer {{ margin-top:40px; font-size:0.9rem; color:#94a3b8; text-align:center; }}
  </style>
</head>
<body>
  <div class=\"container\">
    <header>
      <a href=\"/\" style=\"text-decoration:none;color:#38bdf8;\">← Back to feed</a>
      <h1>{title}</h1>
      <div class=\"meta\">{metadata_html}</div>
    </header>
    {summary_html}
    <article class=\"article-body\">
      {body_html}
    </article>
    {events_html}
    <footer>Source path: {html.escape(article.get('source_url') or article.get('source_file') or 'n/a')}</footer>
  </div>
</body>
</html>
"""
    return template

# API Routes
@app.get("/")
async def serve_index():
    """Serve the simple frontend index page."""
    return FileResponse(path=str((__file__).replace("api.py", "static/index.html")))

# Mount static assets (JS/CSS)
app.mount(
    "/static",
    StaticFiles(directory=str((__file__).replace("api.py", "static"))),
    name="static",
)


@app.get("/articles/{article_id}/source")
async def get_article_source(
    article_id: int,
    service: SummarizationService = Depends(get_service)
):
    """Stream the original article source file from MinIO."""
    article = await service.db_manager.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    source_path = article.get('source_url') or article.get('url') or article.get('source_file')
    raw_html = article.get('raw_html')
    if raw_html or article.get('content'):
        html_page = build_source_page(article)
        return HTMLResponse(content=html_page)

    if not service.minio_client or not source_path:
        raise HTTPException(status_code=404, detail="Article source not available")

    try:
        obj = await asyncio.to_thread(
            service.minio_client.get_object,
            service.minio_bucket,
            source_path,
        )
    except S3Error as exc:
        raise HTTPException(status_code=404, detail=f"Unable to fetch source: {exc}") from exc

    def iterfile():
        try:
            for chunk in obj.stream(32 * 1024):
                yield chunk
        finally:
            obj.close()
            obj.release_conn()

    is_pdf = source_path.lower().endswith(".pdf")
    media_type = "application/pdf" if is_pdf else "application/octet-stream"
    headers = {"Content-Disposition": f"inline; filename={Path(source_path).name}"}
    return StreamingResponse(iterfile(), media_type=media_type, headers=headers)

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


# -------- Feed Endpoints (for simple frontend) --------
@app.get("/feed/dates")
async def get_feed_dates(
    limit: int = 14,
    service: SummarizationService = Depends(get_service)
):
    """Return recent dates that have articles with counts."""
    data = await service.db_manager.get_feed_dates(limit)
    return {"dates": data}


@app.get("/feed")
async def get_feed(
    date_str: Optional[str] = None,
    limit: int = 50,
    section: Optional[str] = None,
    q: Optional[str] = None,
    service: SummarizationService = Depends(get_service)
):
    """Return a list of articles + summaries for the selected date."""
    target_date = None
    if date_str:
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format; use YYYY-MM-DD")
    else:
        target_date = date.today()

    items = await service.db_manager.get_feed_articles(
        target_date=target_date,
        limit=limit,
        section=section,
        search=q,
    )
    return {"date": target_date.isoformat(), "count": len(items), "items": items}


@app.get("/events")
async def get_events(
    days: int = 30,
    service: SummarizationService = Depends(get_service)
):
    """Return upcoming community events derived from articles."""
    events = await service.db_manager.get_events(days)
    grouped: Dict[str, List[Dict]] = {}
    for event in events:
        key = event['start_time'][:10] if event.get('start_time') else 'unscheduled'
        grouped.setdefault(key, []).append(event)
    return {"days": days, "events": grouped}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
