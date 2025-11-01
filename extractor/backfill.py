#!/usr/bin/env python3
"""Backfill cached editions over a date range."""

import argparse
import asyncio
from datetime import datetime, timedelta

from extractor.processor import ExtractionProcessor


def parse_date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


async def process_range(start: datetime.date, end: datetime.date, force: bool):
    processor = ExtractionProcessor()
    await processor.initialize()
    try:
        current = start
        while current <= end:
            await processor.process_cached_edition(current, force_reprocess=force)
            current += timedelta(days=1)
    finally:
        await processor.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill cached editions")
    parser.add_argument("start", type=parse_date, help="Start date (YYYY-MM-DD)")
    parser.add_argument("end", type=parse_date, help="End date (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true", help="Reprocess even if already processed")
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("Start date must be before end date")
    asyncio.run(process_range(args.start, args.end, args.force))


if __name__ == "__main__":
    main()
