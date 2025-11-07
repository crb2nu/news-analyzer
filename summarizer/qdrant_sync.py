#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

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


async def embed_texts_with_fallback(texts: List[str]) -> List[List[float]]:
    from embeddings import embed_with_fallback
    return await embed_with_fallback(texts)


async def main():
    import argparse
    p = argparse.ArgumentParser(description="Sync summarized articles to Qdrant")
    p.add_argument('--hours', type=int, default=int(os.getenv('QDRANT_SYNC_HOURS', '12')))
    args = p.parse_args()

    settings = Settings()
    db = DatabaseManager(settings.database_url)
    await db.initialize()
    try:
        qdrant_url = os.getenv('QDRANT_URL')
        qdrant_key = os.getenv('QDRANT_API_KEY')
        if not qdrant_url:
            raise SystemExit('QDRANT_URL not set')
        client = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=20.0)

        articles = await fetch_articles(db, hours=args.hours)
        if not articles:
            logger.info('No updated summarized articles to sync')
            return

        try:
            texts = [f"{a['title']}\n\n{a['summary'] or a['content'][:2000]}" for a in articles]
            vectors = await embed_texts_with_fallback(texts)
        except Exception as e:
            logger.warning('Embedding failed (%s); Qdrant sync skipped', e.__class__.__name__)
            return

        # Create collection if needed
        dim = len(vectors[0])
        coll = 'articles'
        try:
            client.get_collection(coll)
        except Exception:
            client.recreate_collection(collection_name=coll, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))

        points = []
        for i, a in enumerate(articles):
            payload = {
                'article_id': a['id'],
                'title': a['title'],
                'section': a['section'],
                'summary': a['summary'],
                'content': a['content'],
            }
            if a.get('date_published'):
                payload['date_published'] = a['date_published']
            points.append(PointStruct(id=a['id'], vector=vectors[i], payload=payload))

        logger.info('Upserting %d points into Qdrant', len(points))
        client.upsert(collection_name=coll, points=points, wait=True)
        logger.info('Qdrant sync complete')
    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(main())
