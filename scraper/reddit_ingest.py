"""
Reddit ingestion for local subreddits.

Usage:
  python -m scraper.reddit_ingest --since 24 --limit 50

Env/config:
  REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET (for app auth)
  REDDIT_APP_TYPE = client_credentials | script
  REDDIT_USERNAME, REDDIT_PASSWORD (if script)
  REDDIT_USER_AGENT (recommended)
  REDDIT_SUBREDDITS = comma-separated list (e.g., AbingdonVA,Roanoke,Blacksburg)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
import time

import os
import json
import asyncpg
from .config import Settings as ScraperSettings


logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
BASE_API = "https://oauth.reddit.com"


def _basic_auth(client_id: str, client_secret: Optional[str]) -> Dict[str, str]:
    import base64
    tok = f"{client_id}:{client_secret or ''}".encode()
    return {"Authorization": "Basic " + base64.b64encode(tok).decode()}


def get_access_token(settings: ScraperSettings) -> Optional[str]:
    assert settings.reddit_client_id, "REDDIT_CLIENT_ID required"
    headers = {"User-Agent": settings.reddit_user_agent}
    headers.update(_basic_auth(settings.reddit_client_id, settings.reddit_client_secret))

    app_type = (os.getenv("REDDIT_APP_TYPE") or "client_credentials").lower()
    if app_type == "script" and os.getenv("REDDIT_USERNAME") and os.getenv("REDDIT_PASSWORD"):
        data = {
            "grant_type": "password",
            "username": os.getenv("REDDIT_USERNAME"),
            "password": os.getenv("REDDIT_PASSWORD"),
            "scope": "read",
        }
    else:
        # App-only OAuth: include a basic scope to avoid 401 with some app configs
        data = {"grant_type": "client_credentials", "scope": "read"}

    try:
        resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=20)
        if resp.status_code != 200:
            logger.warning("Token request failed: %s %s", resp.status_code, resp.text[:120])
            return None
        return resp.json().get("access_token")
    except Exception as exc:
        logger.warning("Token request error: %s", exc)
        return None


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def subreddit_list(settings: ScraperSettings) -> List[str]:
    if settings.reddit_subreddits:
        return [s.strip() for s in settings.reddit_subreddits.split(",") if s.strip()]
    # Default seed list for SWVA region (can be adjusted via env)
    return [
        "AbingdonVA",
        "BristolTN",
        "BristolVA",
        "Roanoke",
        "Blacksburg",
        "Christiansburg",
        "Virginiatech",  # campus news
        "Virginia",
        "wythecounty",  # may be small or inactive
    ]


def fetch_subreddit_new(access_token: Optional[str], user_agent: str, sub: str, limit: int = 50) -> List[Dict[str, Any]]:
    if access_token:
        url = f"{BASE_API}/r/{sub}/new"
        headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
    else:
        url = f"https://www.reddit.com/r/{sub}/new.json"
        headers = {"User-Agent": user_agent}
    resp = requests.get(url, headers=headers, params={"limit": str(limit)}, timeout=30)
    if resp.status_code != 200:
        logger.warning("Fetch %s failed: %s", sub, resp.text[:200])
        return []
    data = resp.json()
    # oauth returns Listing in ['data']['children']; .json returns similar
    children = data.get("data", {}).get("children", [])
    return [i.get("data", {}) for i in children]


def fetch_comments(access_token: Optional[str], user_agent: str, post_id: str, limit: int = 50) -> List[str]:
    if access_token:
        url = f"{BASE_API}/comments/{post_id}"
        headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
    else:
        url = f"https://www.reddit.com/comments/{post_id}.json"
        headers = {"User-Agent": user_agent}
    resp = requests.get(url, headers=headers, params={"limit": str(limit), "depth": "1", "sort": "confidence"}, timeout=30)
    if resp.status_code != 200:
        return []
    try:
        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return []
        comments = []
        for child in payload[1].get("data", {}).get("children", []):
            d = child.get("data", {})
            if d.get("body") and not d.get("stickied") and int(d.get("score", 0)) >= 1:
                comments.append(d["body"])
        return comments[:5]
    except Exception:
        return []


async def _get_pool(db_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(db_url, min_size=1, max_size=5)


async def store_posts(posts: List[Dict[str, Any]], sub: str, pool: asyncpg.Pool):
    # Transform and insert into DB (articles table)
    new_count = 0
    for p in posts:
        title = p.get("title") or ""
        body = p.get("selftext") or ""
        permalink = p.get("permalink") or ""
        created = datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc)
        score = p.get("score", 0)
        num_comments = p.get("num_comments", 0)
        url = f"https://www.reddit.com{permalink}" if permalink else p.get("url")

        # Prefer selftext; for link posts, capture the outbound URL inline
        content = body.strip()
        if not content and p.get("url"):
            content = f"Link: {p['url']}\n\n(See discussion in thread)"

        # Basic hash for dedupe
        content_hash = md5(title + content + (url or ""))
        metadata = {
            "subreddit": sub,
            "score": score,
            "num_comments": num_comments,
        }
        tags_json = None
        metadata_json = json.dumps(metadata)

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
                content,
                content_hash,
                url,
                "reddit",
                url,
                f"Reddit/{sub}",
                p.get("author"),
                tags_json,
                len(content.split()),
                created,
                metadata_json,
            )
            new_count += 1
    return new_count


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Reddit posts from local subreddits")
    parser.add_argument("--since", type=int, default=24, help="Hours back to consider")
    parser.add_argument("--limit", type=int, default=50, help="Max posts per subreddit")
    parser.add_argument("--include-comments", action="store_true", help="Append top comments into content")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    class _Cfg:
        reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        reddit_user_agent = os.getenv("REDDIT_USER_AGENT", "news-analyzer/0.1 (by u/localnewsbot)")
        reddit_subreddits = os.getenv("REDDIT_SUBREDDITS")

    scr_settings = _Cfg()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is required for reddit_ingest")
    pool = await _get_pool(db_url)

    try:
        token = get_access_token(scr_settings)
        subs = subreddit_list(scr_settings)
        logger.info("Targeting subreddits: %s", ", ".join(subs))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.since)

        for idx, sub in enumerate(subs):
            if idx > 0:
                time.sleep(2)  # stay under Reddit's 1 req / 2s guidance
            items = fetch_subreddit_new(token, scr_settings.reddit_user_agent, sub, args.limit)
            recent = [p for p in items if datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc) >= cutoff]

            if args.include_comments:
                for p in recent:
                    cid = p.get("id")
                    if cid and not p.get("selftext"):
                        # add a few comments to flesh out link posts
                        time.sleep(2)
                        comments = fetch_comments(token, scr_settings.reddit_user_agent, cid)[:3]
                        if comments:
                            p["selftext"] = (p.get("selftext") or "") + "\n\nTop comments:\n- " + "\n- ".join(comments)

            await store_posts(recent, sub, pool)

        logger.info("Reddit ingestion complete")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
