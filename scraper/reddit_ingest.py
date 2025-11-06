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

from extractor.database import DatabaseManager, StoredArticle
from extractor.config import Settings as ExtractorSettings
from .config import Settings as ScraperSettings


logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
BASE_API = "https://oauth.reddit.com"


def _basic_auth(client_id: str, client_secret: Optional[str]) -> Dict[str, str]:
    import base64
    tok = f"{client_id}:{client_secret or ''}".encode()
    return {"Authorization": "Basic " + base64.b64encode(tok).decode()}


def get_access_token(settings: ScraperSettings) -> str:
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
        data = {"grant_type": "client_credentials"}

    resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Reddit token error {resp.status_code}: {resp.text[:200]}")
    return resp.json().get("access_token")


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


def fetch_subreddit_new(access_token: str, user_agent: str, sub: str, limit: int = 50) -> List[Dict[str, Any]]:
    url = f"{BASE_API}/r/{sub}/new"
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
    resp = requests.get(url, headers=headers, params={"limit": str(limit)}, timeout=30)
    if resp.status_code != 200:
        logger.warning("Fetch %s failed: %s", sub, resp.text[:200])
        return []
    data = resp.json()
    return [i["data"] for i in data.get("data", {}).get("children", [])]


def fetch_comments(access_token: str, user_agent: str, post_id: str, limit: int = 50) -> List[str]:
    url = f"{BASE_API}/comments/{post_id}"
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": user_agent}
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


async def store_posts(posts: List[Dict[str, Any]], sub: str, db: DatabaseManager):
    # Transform into StoredArticle list
    articles: List[StoredArticle] = []
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
        articles.append(
            StoredArticle(
                id=0,
                title=title,
                content=content,
                content_hash=content_hash,
                url=url,
                source_type="reddit",
                source_url=url,
                section=f"Reddit/{sub}",
                author=p.get("author"),
                tags=None,
                word_count=len(content.split()),
                date_published=created,
                date_extracted=datetime.now(timezone.utc),
                raw_html=None,
                metadata={
                    "subreddit": sub,
                    "score": score,
                    "num_comments": num_comments,
                },
            )
        )

    await db.store_articles(articles, source_identifier=f"r/{sub}", source_type="reddit")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Reddit posts from local subreddits")
    parser.add_argument("--since", type=int, default=24, help="Hours back to consider")
    parser.add_argument("--limit", type=int, default=50, help="Max posts per subreddit")
    parser.add_argument("--include-comments", action="store_true", help="Append top comments into content")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    scr_settings = ScraperSettings()
    ext_settings = ExtractorSettings()
    db = DatabaseManager(ext_settings.database_url)
    await db.initialize()

    try:
        token = get_access_token(scr_settings)
        subs = subreddit_list(scr_settings)
        logger.info("Targeting subreddits: %s", ", ".join(subs))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.since)

        for sub in subs:
            items = fetch_subreddit_new(token, scr_settings.reddit_user_agent, sub, args.limit)
            recent = [p for p in items if datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc) >= cutoff]

            if args.include_comments:
                for p in recent:
                    cid = p.get("id")
                    if cid and not p.get("selftext"):
                        # add a few comments to flesh out link posts
                        comments = fetch_comments(token, scr_settings.reddit_user_agent, cid)[:3]
                        if comments:
                            p["selftext"] = (p.get("selftext") or "") + "\n\nTop comments:\n- " + "\n- ".join(comments)

            await store_posts(recent, sub, db)

        logger.info("Reddit ingestion complete")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())

