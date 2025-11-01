import re
from typing import Dict, List, Optional

from dateparser.search import search_dates

WEEKDAY_PATTERN = re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", re.IGNORECASE)
LOCATION_PATTERN = re.compile(r"\b(?:at|in|inside|outside|on)\s+([A-Z][^.,;\n]+)", re.IGNORECASE)


def extract_events(text: str) -> List[Dict]:
    """Extract candidate events from article text."""
    events: List[Dict] = []
    if not text:
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

    for snippet, dt in matches:
        if dt is None:
            continue
        if dt.year < 2000 or dt.year > 2050:
            continue
        key = (dt.isoformat(), snippet.strip())
        if key in seen_times:
            continue
        seen_times.add(key)

        context = _extract_context(text, snippet)
        location = extract_location(context)

        events.append(
            {
                "title": context.strip()[:200] or snippet.strip(),
                "start_time": dt.isoformat(),
                "location_name": location,
                "context": context.strip(),
            }
        )

    return events


def extract_location(text: str) -> Optional[str]:
    if not text:
        return None
    match = LOCATION_PATTERN.search(text)
    if match:
        candidate = match.group(1).strip()
        candidate = re.sub(r"\s+", " ", candidate)
        return candidate[:200]
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
