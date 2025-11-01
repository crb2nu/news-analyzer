import argparse
import datetime as dt
import pathlib
from typing import List

from .config import Settings
from .facebook_client import FacebookClient


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch posts/events from Facebook Pages you manage (via Graph API)")
    p.add_argument("--since", help="ISO date (YYYY-MM-DD) to fetch from", default=None)
    p.add_argument("--pages", help="Comma-separated page IDs to override config", default=None)
    p.add_argument("--out", help="Output directory base", default="cache/facebook")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings()
    client = FacebookClient(settings)

    if args.pages:
        pages: List[str] = [p.strip() for p in args.pages.split(",") if p.strip()]
    else:
        pages = settings.list_facebook_pages()

    if not pages:
        print("No pages configured. Set FACEBOOK_PAGE_IDS or pass --pages.")
        return 2

    since_dt = None
    if args.since:
        since_dt = dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc)

    today = dt.datetime.now(dt.timezone.utc).date()
    base = pathlib.Path(args.out) / str(today) / "raw"

    total_posts = 0
    total_events = 0

    for page_id in pages:
        posts_path = base / f"{page_id}_posts.jsonl"
        events_path = base / f"{page_id}_events.jsonl"

        posts = list(client.fetch_page_posts(page_id, since=since_dt))
        total_posts += client.write_jsonl(posts_path, posts)

        events = list(client.fetch_page_events(page_id, since=since_dt))
        total_events += client.write_jsonl(events_path, events)

        print(f"Page {page_id}: wrote {len(posts)} posts to {posts_path}")
        print(f"Page {page_id}: wrote {len(events)} events to {events_path}")

    print(f"Done. Posts: {total_posts}, Events: {total_events}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

