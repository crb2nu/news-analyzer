"""
NWS Alerts ingestion (OSINT).

Fetch active weather alerts for configured zones or a bounding box and
store them as articles for summarization.

Usage:
  python -m scraper.nws_ingest --zone VAZ022 --zone VAZ023
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import List

import requests

import os
import json
import asyncpg

logger = logging.getLogger(__name__)


def md5(s: str) -> str:
    import hashlib as _h
    return _h.md5(s.encode("utf-8")).hexdigest()


def fetch_alerts(zones: List[str]) -> list[dict]:
    # API: https://api.weather.gov/alerts/active?zone=VAZ022
    alerts = []
    for z in zones:
        url = "https://api.weather.gov/alerts/active"
        try:
            resp = requests.get(url, params={"zone": z}, headers={"User-Agent": "news-analyzer/0.1"}, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                for feat in data.get("features", []):
                    alerts.append(feat)
        except Exception as exc:
            logger.warning("NWS fetch failed for %s: %s", z, exc)
    return alerts


async def _get_pool(db_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(db_url, min_size=1, max_size=5)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest NWS active alerts")
    parser.add_argument("--zone", action="append", dest="zones", help="Zone ID (e.g., VAZ022)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    zones = args.zones or []
    if not zones:
        # Smyth (VAZ022), Washington (VAZ023), Wythe (VAZ024) typical AFO RNK examples
        zones = ["VAZ022", "VAZ023", "VAZ024"]

    alerts = fetch_alerts(zones)
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is required for nws_ingest")
    pool = await _get_pool(db_url)

    try:
        new_count = 0
        for feat in alerts:
            props = feat.get("properties", {})
            title = props.get("headline") or props.get("event") or "NWS Alert"
            desc = props.get("description") or ""
            instr = props.get("instruction")
            body = desc + (f"\n\nInstructions: {instr}" if instr else "")
            url = props.get("@id")
            issued = props.get("onset") or props.get("effective") or props.get("sent")
            dt = None
            try:
                if issued:
                    dt = datetime.fromisoformat(issued.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)

            ch = md5((title or "") + body + (url or ""))
            metadata = {"severity": props.get("severity"), "areaDesc": props.get("areaDesc")}
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO articles (
                        title, content, content_hash, url, source_type, source_url,
                        section, author, tags, word_count, date_published,
                        date_extracted, processing_status, raw_html, metadata
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6,
                        $7, $8, $9, $10, $11,
                        NOW(), 'extracted', NULL, $12
                    ) ON CONFLICT (content_hash) DO NOTHING
                    """,
                    title,
                    body,
                    ch,
                    url,
                    "osint",
                    url,
                    "NWS Alerts",
                    "NWS",
                    None,
                    len(body.split()),
                    dt,
                    json.dumps(metadata),
                )
                new_count += 1

        if new_count:
            logger.info("Stored %d NWS alerts", new_count)
        else:
            logger.info("No NWS alerts")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
