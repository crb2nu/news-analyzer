#!/usr/bin/env python3
"""
Weaviate sync job: upsert summarized articles from Postgres into Weaviate.
Uses BM25 by default (vectorizer: none). If OPENAI_EMBED_MODEL is set, will
generate vectors via OpenAI embeddings and include them on upsert.
"""
from __future__ import annotations

import asyncio
import os
import logging
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional
import uuid

import httpx

try:
    from summarizer.database import DatabaseManager
    from summarizer.config import Settings
except Exception:
    from database import DatabaseManager
    from config import Settings

try:
    from openai import AsyncOpenAI
except Exception:
    AsyncOpenAI = None  # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


CLASS_NAME = "Article"

def _weaviate_request(method: str, base_url: str, path: str, **kwargs):
    url = base_url.rstrip('/') + path
    headers = kwargs.pop('headers', {}) or {}
    api_key = os.getenv('WEAVIATE_API_KEY')
    if api_key:
        headers.setdefault('Authorization', f'Bearer {api_key}')
        headers.setdefault('X-API-KEY', api_key)
    with httpx.Client(timeout=30.0) as client:
        resp = client.request(method, url, headers=headers, **kwargs)
        if resp.status_code >= 400:
            try:
                detail = resp.text
            except Exception:
                detail = '<no-body>'
            raise httpx.HTTPStatusError(
                f"{resp.status_code} {resp.reason_phrase}: {detail[:500]}", request=resp.request, response=resp
            )
        return resp.json() if resp.content else None


async def fetch_articles(db: DatabaseManager, hours: int = 12) -> List[Dict[str, Any]]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    sql = """
        SELECT a.id, a.title, a.section, a.content, a.date_published,
               COALESCE(s.summary_text, '') AS summary_text,
               a.date_updated
        FROM articles a
        LEFT JOIN LATERAL (
            SELECT summary_text
            FROM summaries s
            WHERE s.article_id = a.id AND s.summary_type = 'brief'
            ORDER BY s.date_created DESC
            LIMIT 1
        ) s ON TRUE
        WHERE a.processing_status = 'summarized' AND a.date_updated >= $1
        ORDER BY a.date_updated DESC
        LIMIT 1000
    """
    async with db.get_connection() as conn:
        rows = await conn.fetch(sql, cutoff)
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append({
                'id': int(r['id']),
                'title': r['title'],
                'section': r['section'] or 'General',
                'content': r['content'],
                'summary': r['summary_text'] or '',
                'date_published': r['date_published'].isoformat() if r['date_published'] else None,
            })
        return out


async def embed_texts(texts: List[str]) -> List[List[float]]:
    from embeddings import embed_with_fallback
    return await embed_with_fallback(texts)


def ensure_class_rest(base_url: str) -> None:
    schema = _weaviate_request('GET', base_url, '/v1/schema')
    if any(c.get('class') == CLASS_NAME for c in schema.get('classes', [])):
        return
    payload = {
        'class': CLASS_NAME,
        'vectorizer': 'none',
        'properties': [
            {'name': 'article_id', 'dataType': ['int']},
            {'name': 'title', 'dataType': ['text']},
            {'name': 'section', 'dataType': ['text']},
            {'name': 'summary', 'dataType': ['text']},
            {'name': 'content', 'dataType': ['text']},
            {'name': 'date_published', 'dataType': ['date']},
        ],
        'moduleConfig': {'bm25': {}},
    }
    _weaviate_request('POST', base_url, '/v1/schema', json=payload)


async def main():
    import argparse
    p = argparse.ArgumentParser(description="Sync summarized articles to Weaviate")
    p.add_argument('--hours', type=int, default=int(os.getenv('WEAVIATE_SYNC_HOURS', '12')))
    args = p.parse_args()

    settings = Settings()
    db = DatabaseManager(settings.database_url)
    await db.initialize()

    try:
        weaviate_url = os.getenv('WEAVIATE_URL') or settings.__dict__.get('weaviate_url')
        if not weaviate_url:
            raise SystemExit('WEAVIATE_URL not set')
        ensure_class_rest(weaviate_url)

        articles = await fetch_articles(db, hours=args.hours)
        if not articles:
            logger.info('No updated summarized articles to sync')
            return

        # Optional OpenAI embeddings
        vectors: Optional[List[List[float]]] = None
        try:
            texts = [f"{a['title']}\n\n{a['summary'] or a['content'][:2000]}" for a in articles]
            vectors = await embed_texts(texts)
        except Exception as e:
            logger.warning("Embedding failed (%s); continuing with BM25 only", e.__class__.__name__)
            vectors = None

        logger.info('Upserting %d articles to Weaviate (vectors=%s)', len(articles), bool(vectors))
        objs = []
        for i, a in enumerate(articles):
            props = {
                'article_id': a['id'],
                'title': a['title'],
                'section': a['section'],
                'summary': a['summary'],
                'content': a['content'],
            }
            if a.get('date_published'):
                props['date_published'] = a['date_published']
            # Deterministic UUID from article id for idempotent upserts
            wid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"article:{a['id']}"))
            obj = {'class': CLASS_NAME, 'id': wid, 'properties': props}
            if vectors:
                obj['vector'] = vectors[i]
            objs.append(obj)
        _weaviate_request('POST', weaviate_url, '/v1/batch/objects', json={'objects': objs})

        logger.info('Weaviate sync complete')
    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
