import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from dateparser.search import search_dates

WEEKDAY_PATTERN = re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", re.IGNORECASE)
MONTH_PATTERN = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)\b", re.IGNORECASE)
DATE_NUMERIC = re.compile(r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/(20\d{2})\b")
TIME_PATTERN = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s?(am|pm|a\.m\.|p\.m\.)\b", re.IGNORECASE)
LOCATION_PATTERN = re.compile(r"\b(?:at|in|inside|outside|on)\s+([A-Z][^.,;\n]{2,80})", re.IGNORECASE)


def extract_events(text: str) -> List[Dict]:
    """Extract candidate events from article text (strict heuristics).

    We favor precision over recall to avoid hallucinated or irrelevant dates.
    """
    events: List[Dict] = []
    if not text:
        return events

    # Quick reject for obviously non-calendar content (headlines/boilerplate)
    if text.strip().lower().startswith("key points:"):
        return events

    matches = search_dates(
        text,
        settings={
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DATES_FROM": "future",
        },
    )
    if not matches:
        return events

    seen_times = set()
    now = datetime.utcnow()
    future_limit = now + timedelta(days=365)  # ignore dates more than a year out

    for snippet, dt in matches:
        if not dt:
            continue
        # Filter implausible years
        if dt.year < 2000 or dt.year > 2050:
            continue
        # Ignore far-future dates
        if dt > future_limit:
            continue

        context = _extract_context(text, snippet)
        ctx = context.strip()
        if not ctx:
            continue

        # Heuristics to avoid non-event narrative
        too_long = len(ctx) > 220
        has_weekday_or_month = bool(WEEKDAY_PATTERN.search(ctx) or MONTH_PATTERN.search(ctx) or DATE_NUMERIC.search(ctx))
        has_time_or_at = bool(TIME_PATTERN.search(ctx) or re.search(r"\b(at|from)\b", ctx, re.IGNORECASE))
        looks_like_bullets = ctx.lower().startswith(("key points", "sentiment"))
        contains_money = re.search(r"\$\s?\d", ctx)

        # Require date signal AND a simple location/time cue; reject noisy lines
        if too_long or not has_weekday_or_month or not has_time_or_at or looks_like_bullets or contains_money:
            continue

        location = extract_location(ctx)

        key = (dt.replace(second=0, microsecond=0).isoformat(), ctx[:80])
        if key in seen_times:
            continue
        seen_times.add(key)

        events.append(
            {
                "title": ctx[:200],
                "start_time": dt.isoformat(),
                "location_name": location,
                "context": ctx,
            }
        )

        if len(events) >= 5:  # cap to avoid spammy articles
            break

    return events


def extract_location(text: str) -> Optional[str]:
    if not text:
        return None
    match = LOCATION_PATTERN.search(text)
    if match:
        candidate = match.group(1).strip()
        candidate = re.sub(r"\s+", " ", candidate)
        # Trim trailing fillers
        candidate = re.sub(r"\s+(and|with|for)\b.*$", "", candidate, flags=re.IGNORECASE)
        return candidate[:120]
    return None


def _extract_context(full_text: str, snippet: str, window: int = 160) -> str:
    idx = full_text.lower().find(snippet.lower())
    if idx == -1:
        idx = 0
    start = max(0, idx - window)
    end = min(len(full_text), idx + len(snippet) + window)
    context = full_text[start:end]
    # Trim to sentence boundaries if possible
    before = context.rfind(". ")
    if before != -1 and before > window // 2:
        context = context[before + 2 :]
    after = context.find(". ")
    if after != -1 and after > len(snippet):
        context = context[: after + 1]
    return context
