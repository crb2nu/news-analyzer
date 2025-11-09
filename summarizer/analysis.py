#!/usr/bin/env python3
"""
Lightweight analytics job: aggregates daily metrics (tags, entities, topics, sections),
computes simple trending scores, and stores results for UI consumption.

Usage:
  python -m summarizer.analysis --window 7 --days 3
"""

from __future__ import annotations

import asyncio
import os
import logging
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

from pydantic import BaseModel

try:
    from summarizer.database import DatabaseManager
    from summarizer.config import Settings
except Exception:
    from database import DatabaseManager
    from config import Settings


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AnalysisJob:
    def __init__(self, window: int = 7, days: int = 3):
        self.window = window
        self.days = days
        self.settings = Settings()
        self.db = DatabaseManager(self.settings.database_url)

    async def initialize(self):
        await self.db.initialize()

    async def close(self):
        await self.db.close()

    async def _aggregate_for_day(self, d: date) -> None:
        """Aggregate daily counts into daily_metrics."""
        sql = """
        WITH base AS (
            SELECT $1::date AS day
        ),
        a AS (
            SELECT * FROM articles WHERE DATE(date_extracted) = $1::date
        ),
        by_section AS (
            SELECT $1::date AS day, 'section' AS kind, COALESCE(NULLIF(section,''),'General') AS key, COUNT(*)::int AS cnt, NULL::real AS sum_score
            FROM a GROUP BY key
        ),
        by_publication AS (
            SELECT $1::date AS day, 'publication' AS kind, COALESCE(NULLIF(publication,''),'(unknown)') AS key, COUNT(*)::int AS cnt, NULL::real AS sum_score
            FROM a GROUP BY key
        ),
        by_tag AS (
            SELECT $1::date AS day, 'tag' AS kind, t.tag AS key, COUNT(*)::int AS cnt, NULL::real AS sum_score
            FROM a JOIN article_tags t ON t.article_id = a.id
            GROUP BY t.tag
        ),
        by_topic AS (
            SELECT $1::date AS day, 'topic' AS kind, tp.label AS key, COUNT(*)::int AS cnt, SUM(at.score)::real AS sum_score
            FROM a JOIN article_topics at ON at.article_id = a.id
                   JOIN topics tp ON tp.id = at.topic_id
            GROUP BY tp.label
        ),
        by_entity AS (
            SELECT $1::date AS day, 'entity' AS kind, e.name AS key, COUNT(*)::int AS cnt, NULL::real AS sum_score
            FROM a JOIN article_entities ae ON ae.article_id = a.id
                   JOIN entities e ON e.id = ae.entity_id
            GROUP BY e.name
        ),
        unioned AS (
            SELECT * FROM by_section
            UNION ALL SELECT * FROM by_tag
            UNION ALL SELECT * FROM by_topic
            UNION ALL SELECT * FROM by_entity
            UNION ALL SELECT * FROM by_publication
        )
        INSERT INTO daily_metrics(metric_date, kind, key, count, sum_score)
        SELECT day, kind, key, cnt, sum_score FROM unioned
        ON CONFLICT (metric_date, kind, key)
        DO UPDATE SET count = EXCLUDED.count, sum_score = EXCLUDED.sum_score, created_at = NOW();
        """
        async with self.db.get_connection() as conn:
            await conn.execute(sql, d)

    async def _compute_trending_for_day(self, d: date) -> None:
        """Compute trend z-scores vs trailing window and store in trending_items."""
        sql = """
        WITH cur AS (
            SELECT kind, key, count::real AS c
            FROM daily_metrics WHERE metric_date = $1::date
        ), hist AS (
            SELECT kind, key, AVG(count)::real AS mean_c, STDDEV_POP(count)::real AS std_c
            FROM daily_metrics
            WHERE metric_date BETWEEN $1::date - ($2::int || ' days')::interval AND $1::date - INTERVAL '1 day'
            GROUP BY kind, key
        ), joined AS (
            SELECT c.kind, c.key,
                   c.c,
                   COALESCE(h.mean_c, 0.0) AS mean_c,
                   COALESCE(NULLIF(h.std_c,0.0), 1.0) AS std_c
            FROM cur c LEFT JOIN hist h ON h.kind = c.kind AND h.key = c.key
        )
        INSERT INTO trending_items(metric_date, kind, key, score, zscore, win_size, delta, details)
        SELECT $1::date, kind, key,
               (c - mean_c) AS score,
               (c - mean_c) / std_c AS z,
               $2::int AS win_size,
               (c - mean_c) AS delta,
               jsonb_build_object('current', c, 'mean', mean_c, 'std', std_c)
        FROM joined
        ON CONFLICT (metric_date, kind, key) DO UPDATE SET
            score = EXCLUDED.score,
            zscore = EXCLUDED.zscore,
            win_size = EXCLUDED.win_size,
            delta = EXCLUDED.delta,
            details = EXCLUDED.details,
            created_at = NOW();
        """
        async with self.db.get_connection() as conn:
            await conn.execute(sql, d, self.window)

    async def _compute_forecasts(self, d: date, kind: str = 'tag', top_n: int = 5, horizon: int = 7) -> None:
        """Very simple baseline forecast: next h days = trailing 7-day mean.

        Stores into trend_forecasts for UI experimentation.
        """
        fetch_sql = """
            WITH recent AS (
                SELECT key, metric_date, count::real AS c
                FROM daily_metrics
                WHERE kind = $1 AND metric_date BETWEEN $2::date - INTERVAL '28 days' AND $2::date
            ), latest AS (
                SELECT key, SUM(CASE WHEN metric_date > $2::date - INTERVAL '7 days' THEN c ELSE 0 END) / 7.0 AS mean7
                FROM recent
                GROUP BY key
                ORDER BY mean7 DESC
                LIMIT $3
            )
            SELECT r.key, COALESCE(l.mean7, 0.0) AS mean7
            FROM latest l JOIN (SELECT DISTINCT key FROM recent) r ON r.key = l.key
        """

        async with self.db.get_connection() as conn:
            rows = await conn.fetch(fetch_sql, kind, d, top_n)
            for row in rows:
                k = row['key']
                mean7 = float(row['mean7'] or 0.0)
                series = []
                for i in range(1, horizon + 1):
                    tgt = d + timedelta(days=i)
                    series.append({'date': tgt.isoformat(), 'yhat': mean7})
                await conn.execute(
                    """
                    INSERT INTO trend_forecasts(date_generated, kind, key, horizon_days, forecast)
                    VALUES($1,$2,$3,$4,$5::jsonb)
                    ON CONFLICT (date_generated, kind, key, horizon_days)
                    DO UPDATE SET forecast = EXCLUDED.forecast, created_at = NOW()
                    """,
                    d,
                    kind,
                    k,
                    horizon,
                    json.dumps(series),
                )

    async def run(self):
        today = date.today()
        start = today - timedelta(days=self.days - 1)
        for i in range(self.days):
            day = start + timedelta(days=i)
            logger.info("Aggregating metrics for %s", day.isoformat())
            await self._aggregate_for_day(day)
            await self._compute_trending_for_day(day)
        # generate quick forecasts for tags and topics for today
        await self._compute_forecasts(today, kind='tag', top_n=5, horizon=7)
        await self._compute_forecasts(today, kind='topic', top_n=5, horizon=7)


async def main():
    import argparse
    p = argparse.ArgumentParser(description="Daily analysis aggregator")
    p.add_argument('--window', type=int, default=int(os.getenv('ANALYSIS_WINDOW', '7')))
    p.add_argument('--days', type=int, default=int(os.getenv('ANALYSIS_DAYS', '3')))
    args = p.parse_args()

    job = AnalysisJob(window=args.window, days=args.days)
    await job.initialize()
    try:
        await job.run()
    finally:
        await job.close()


if __name__ == '__main__':
    asyncio.run(main())
