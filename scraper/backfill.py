#!/usr/bin/env python3
"""
Scraper backfill over a date range and (optionally) multiple publications.

This orchestrates discovery + download for each requested date and publication,
writing raw pages into the MinIO cache so the extractor can process them.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from .discover import EditionDiscoverer, DEFAULT_PUBLICATION
from .downloader import DownloadCache


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (YYYY-MM-DD)") from exc


def daterange(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def is_likely_publication_day(d: date) -> bool:
    """Heuristic: many weeklies publish Wed/Sat. Keep as best-effort filter.

    Returns True for all days if the heuristic is disabled by the caller.
    """
    return d.weekday() in (2, 5)  # Wed=2, Sat=5


@dataclass
class BackfillConfig:
    start: date
    end: date
    publications: List[str]
    storage_state: Path
    force: bool = False
    only_likely_days: bool = True


def run_backfill(cfg: BackfillConfig) -> int:
    discoverer = EditionDiscoverer(storage_path=cfg.storage_state)
    downloader = DownloadCache()

    total_editions = 0
    total_pages = 0
    total_success = 0

    for d in daterange(cfg.start, cfg.end):
        if cfg.only_likely_days and not is_likely_publication_day(d):
            continue
        for pub in cfg.publications:
            print(f"[backfill] {d.isoformat()} — {pub}")
            edition = discoverer.discover_date(d, publication=pub)
            if not edition:
                print(f"  no edition found")
                continue
            total_editions += 1
            result = downloader.download_edition(edition, force_refresh=cfg.force)
            total_pages += result.get("total_pages", 0)
            total_success += result.get("successful_downloads", 0)
            print(
                "  pages: {ok}/{tot} (cache {cache})".format(
                    ok=result.get("successful_downloads", 0),
                    tot=result.get("total_pages", 0),
                    cache=result.get("cached_pages", 0),
                )
            )

    print(
        f"Done. Editions: {total_editions}, pages downloaded: {total_success}/{total_pages}"
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Scraper backfill over a date range")
    p.add_argument("--start", type=parse_date, required=True, help="Start date YYYY-MM-DD")
    p.add_argument("--end", type=parse_date, required=True, help="End date YYYY-MM-DD")
    p.add_argument(
        "--publication",
        action="append",
        help="Publication name (may repeat). Default is the Smyth County edition.",
    )
    p.add_argument(
        "--all-publications",
        action="store_true",
        help="Process all supported publications",
    )
    p.add_argument(
        "--storage",
        type=Path,
        default=Path("storage_state.json"),
        help="Playwright storage state path",
    )
    p.add_argument("--force", action="store_true", help="Re-download even if cached")
    p.add_argument(
        "--no-day-heuristic",
        action="store_true",
        help="Process all dates (disable Wed/Sat heuristic)",
    )

    args = p.parse_args(argv)
    if args.start > args.end:
        p.error("--start must be on/before --end")

    if args.all_publications:
        pubs = EditionDiscoverer().get_available_publications()
    elif args.publication:
        pubs = list(args.publication)
    else:
        pubs = [DEFAULT_PUBLICATION]

    cfg = BackfillConfig(
        start=args.start,
        end=args.end,
        publications=pubs,
        storage_state=args.storage,
        force=args.force,
        only_likely_days=not args.no_day_heuristic,
    )
    return run_backfill(cfg)


if __name__ == "__main__":
    raise SystemExit(main())

