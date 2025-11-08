#!/usr/bin/env python3
"""Re-run extraction + summarization on cached editions and refresh vector stores."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional


def parse_date_arg(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Use YYYY-MM-DD format") from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extractor.processor import ExtractionProcessor  # noqa: E402
from scraper.downloader import DownloadCache  # noqa: E402
from summarizer.batch import BatchProcessor  # noqa: E402
from summarizer.config import Settings as SummarizerSettings  # noqa: E402
from summarizer.database import DatabaseManager as SummarizerDB  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dates", nargs="+", type=parse_date_arg,
                        help="Explicit edition dates to reprocess (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=parse_date_arg, help="Earliest edition date to include")
    parser.add_argument("--end-date", type=parse_date_arg, help="Latest edition date to include")
    parser.add_argument("--limit", type=int, help="Only process the most recent N dates after filtering")
    parser.add_argument("--force-extract", action="store_true",
                        help="Force re-extraction even if a file was already processed")
    parser.add_argument("--skip-extraction", action="store_true", help="Skip the extraction phase")
    parser.add_argument("--skip-summarizer", action="store_true", help="Skip the summarizer phase")
    parser.add_argument("--resummarize-mode", choices=["missing", "force"], default="force",
                        help="missing=only summarize pending articles; force=reset summarized/notified items in range")
    parser.add_argument("--max-batches", type=int, default=100,
                        help="Maximum summarizer batches to process (default: 100)")
    parser.add_argument("--vector-sync", choices=["auto", "none", "weaviate", "qdrant", "both"], default="auto",
                        help="Which vector targets to refresh after summarizing")
    parser.add_argument("--vector-lookback-hours", type=int, default=48,
                        help="How many recent hours of updates to push to vector stores")
    parser.add_argument("--log-level", default="INFO", help="Python logging level (default: INFO)")
    return parser


def resolve_target_dates(args: argparse.Namespace) -> List[date]:
    """Return the ordered list of edition dates to process."""
    if args.dates:
        base = sorted(set(args.dates))
    else:
        downloader = DownloadCache()
        cached_strings = downloader.list_cached_editions()
        base = sorted(parse_date_arg(value) for value in cached_strings)

    if args.start_date:
        base = [d for d in base if d >= args.start_date]
    if args.end_date:
        base = [d for d in base if d <= args.end_date]

    if args.limit and args.limit > 0:
        base = base[-args.limit:]

    return base


def resolve_range(args: argparse.Namespace, dates: List[date]) -> tuple[Optional[date], Optional[date]]:
    start = args.start_date or (dates[0] if dates else None)
    end = args.end_date or (dates[-1] if dates else None)
    if start and not end:
        end = start
    if end and not start:
        start = end
    if start and end and end < start:
        start, end = end, start
    return start, end


async def run_extraction(dates: List[date], force: bool) -> dict:
    summary = {
        "requested_dates": [d.isoformat() for d in dates],
        "processed": [],
        "total_new": 0,
        "total_duplicates": 0,
        "total_files": 0,
        "failed_dates": [],
    }

    if not dates:
        summary["skipped"] = True
        return summary

    processor = ExtractionProcessor()
    await processor.initialize()
    try:
        for edition_date in dates:
            try:
                result = await processor.process_cached_edition(edition_date, force_reprocess=force)
                summary["processed"].append({
                    "date": edition_date.isoformat(),
                    "files": result.get("processed_files", 0),
                    "new_articles": result.get("new_articles", 0),
                    "duplicates": result.get("duplicate_articles", 0),
                    "skipped_files": result.get("skipped_files", 0),
                })
                summary["total_new"] += result.get("new_articles", 0)
                summary["total_duplicates"] += result.get("duplicate_articles", 0)
                summary["total_files"] += result.get("processed_files", 0)
            except Exception as exc:  # pragma: no cover - defensive
                logging.exception("Extraction failed for %s", edition_date.isoformat())
                summary["failed_dates"].append({"date": edition_date.isoformat(), "error": str(exc)})
    finally:
        await processor.close()

    return summary


async def reset_statuses_for_range(start: date, end: date, mode: str) -> int:
    if mode != "force":
        return 0
    db = SummarizerDB(SummarizerSettings().database_url)
    await db.initialize()
    try:
        return await db.reset_processing_status_for_dates(start, end, ["summarized", "notified"])
    finally:
        await db.close()


async def run_summarizer(max_batches: int) -> dict:
    settings = SummarizerSettings()
    processor = BatchProcessor(settings)
    return await processor.run(max_batches=max_batches)


def resolve_vector_targets(mode: str) -> List[str]:
    if mode == "none":
        return []
    if mode == "both":
        return ["weaviate", "qdrant"]
    if mode in ("weaviate", "qdrant"):
        return [mode]

    targets: List[str] = []
    if mode == "auto":
        if os.getenv("WEAVIATE_URL") or os.getenv("WEAVIATE_ENDPOINT"):
            targets.append("weaviate")
        if os.getenv("QDRANT_URL"):
            targets.append("qdrant")
    return targets


async def run_vector_sync(targets: List[str], hours: int) -> List[dict]:
    if not targets:
        return []

    results: List[dict] = []
    for target in targets:
        module = f"summarizer.{target}_sync"
        cmd = [sys.executable, "-m", module, "--hours", str(hours)]
        logging.info("Running %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(*cmd)
        returncode = await proc.wait()
        results.append({"target": target, "returncode": returncode})
    return results


async def orchestrate(args: argparse.Namespace) -> tuple[int, dict]:
    summary: dict = {}
    target_dates = resolve_target_dates(args)
    range_start, range_end = resolve_range(args, target_dates)

    if args.resummarize_mode == "force" and (range_start is None or range_end is None):
        raise SystemExit("Unable to determine a date range for resummarization. Provide --dates or --start/--end-date.")

    if not args.skip_extraction:
        logging.info("Starting extraction for %d cached edition(s)", len(target_dates))
        summary["extraction"] = await run_extraction(target_dates, args.force_extract)
    else:
        summary["extraction"] = {"skipped": True, "requested_dates": []}

    if args.skip_summarizer:
        summary["summarizer"] = {"skipped": True}
    else:
        if range_start and range_end:
            reset_count = await reset_statuses_for_range(range_start, range_end, args.resummarize_mode)
        else:
            reset_count = 0
        logging.info("Reset %d article(s) to extracted status", reset_count)
        summary["summarizer"] = await run_summarizer(args.max_batches)
        summary["summarizer"]["reset_articles"] = reset_count

    vector_targets = resolve_vector_targets(args.vector_sync)
    if vector_targets:
        summary["vector_sync"] = await run_vector_sync(vector_targets, args.vector_lookback_hours)
    else:
        summary.setdefault("vector_sync", [])

    exit_code = 0
    extraction_failures = summary["extraction"].get("failed_dates") if isinstance(summary["extraction"], dict) else []
    if extraction_failures:
        exit_code = 1
    summarizer_stats = summary.get("summarizer") or {}
    if summarizer_stats.get("error") or summarizer_stats.get("errors", 0) > 0:
        exit_code = 1
    for item in summary.get("vector_sync", []):
        if item.get("returncode") not in (None, 0):
            exit_code = 1

    return exit_code, summary


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(message)s")
    exit_code, summary = asyncio.run(orchestrate(args))
    logging.info("Reprocess summary: %s", summary)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
