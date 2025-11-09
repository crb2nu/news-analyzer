#!/usr/bin/env python3
"""
Emit JSON split windows for a date range.

Usage:
  START=YYYY-MM-DD END=YYYY-MM-DD [SPLIT=weekly|daily|biweekly] scripts/split_range.py
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, date


def main() -> None:
    start_s = os.environ.get("START")
    end_s = os.environ.get("END")
    unit = os.environ.get("SPLIT", "weekly")
    if not start_s or not end_s:
        raise SystemExit("START and END env vars are required")
    start = datetime.strptime(start_s, "%Y-%m-%d").date()
    end = datetime.strptime(end_s, "%Y-%m-%d").date()
    if start > end:
        start, end = end, start

    def next_boundary(d: date) -> tuple[date, date]:
        if unit == "daily":
            return d, d
        if unit == "biweekly":
            return d, min(end, d + timedelta(days=13))
        # weekly default (7-day windows)
        return d, min(end, d + timedelta(days=6))

    splits: list[dict[str, str]] = []
    cur = start
    while cur <= end:
        s, e = next_boundary(cur)
        # only keep windows that include at least one Wed(2)/Sat(5)
        d = s
        keep = False
        while d <= e:
            if d.weekday() in (2, 5):
                keep = True
                break
            d += timedelta(days=1)
        if keep:
            splits.append({"start": s.isoformat(), "end": e.isoformat()})
        cur = e + timedelta(days=1)

    print(json.dumps(splits))


if __name__ == "__main__":
    main()

