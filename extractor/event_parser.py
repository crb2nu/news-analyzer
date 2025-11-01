import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from dateparser.search import search_dates

WEEKDAY_PATTERN = re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", re.IGNORECASE)
MONTH_PATTERN = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)\b", re.IGNORECASE)
DATE_NUMERIC = re.compile(r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/(20\d{2})\b")
TIME_PATTERN = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s?(am|pm|a\.m\.|p\.m\.)\b", re.IGNORECASE)
LOCATION_PATTERN = re.compile(r"\b(?:at|in|inside|outside|on)\s+([A-Z][^.,;\n]{2,80})", re.IGNORECASE)
EVENT_KEYWORDS = re.compile(
    r"\b(meeting|meet|festival|concert|workshop|class|clinic|seminar|webinar|ceremony|parade|game|match|tournament|"
    r"celebration|fundraiser|luncheon|banquet|conference|summit|service|gala|open house|open-house|open\s+house|"
    r"kickoff|cook\-?off|cookoff|trail|race|5k|10k|run|walk|tour|dance|performance|play|screening|market|fair|"
    r"forum|panel|hearing|camp|drive|lecture|symposium|training|workshop|class)\b",
    re.IGNORECASE,
)


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
    future_limit = now + timedelta(days=180)  # ignore dates more than ~6 months out

    for snippet, dt in matches:
        if not dt:
            continue
        # Filter implausible years
        if dt.year < 2000 or dt.year > 2050:
            continue
        # Ignore far-future dates
        if dt > future_limit:
            continue
        # Skip past dates (allow small fudge for same-day timezone differences)
        if dt < now - timedelta(days=1):
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
        has_keyword = bool(EVENT_KEYWORDS.search(ctx))

        # Require event-like keywords plus a date/time cue; reject noisy lines
        if (
            too_long
            or not has_weekday_or_month
            or not has_time_or_at
            or looks_like_bullets
            or contains_money
            or not has_keyword
        ):
            continue

        location = extract_location(ctx)
        if not location:
            # try to derive a short trailing phrase after " at "
            location = _fallback_location(ctx)
        if location:
            location = _sanitize_location(location)

        key = (dt.replace(second=0, microsecond=0).isoformat(), ctx[:80])
        if key in seen_times:
            continue
        seen_times.add(key)

        event_title = _derive_title(ctx)

        events.append(
            {
                "title": event_title,
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
        return _sanitize_location(candidate)
    return None


def _fallback_location(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\bat\s+([^.,;\n]{3,80})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\bin\s+([^.,;\n]{3,80})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _sanitize_location(raw: str) -> str:
    candidate = re.sub(r"\s+", " ", raw).strip(" .,:;")
    candidate = re.sub(r"\s+(and|with|for|featuring)\b.*$", "", candidate, flags=re.IGNORECASE)
    return candidate[:120]


def _derive_title(context: str) -> str:
    if not context:
        return "Community event"
    sentence_end = context.find(". ")
    if sentence_end != -1:
        title = context[: sentence_end + 1]
    else:
        title = context
    title = title.strip()
    if len(title) > 160:
        title = title[:157] + "..."
    return title or "Community event"


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
