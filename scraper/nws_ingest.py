"""NWS alert ingestion for the OSINT pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List

import asyncpg
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://api.weather.gov/alerts/active"
DEFAULT_ZONES = ["VAZ022", "VAZ023", "VAZ024"]
DEFAULT_STATUSES = ["actual"]
DEFAULT_MESSAGE_TYPES = ["alert", "update"]


def md5(value: str) -> str:
    import hashlib as _hashlib

    return _hashlib.md5(value.encode("utf-8")).hexdigest()


def parse_env_list(name: str) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_session(user_agent: str, timeout: int) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/geo+json",
        }
    )
    session.request = _wrap_request_with_timeout(session.request, timeout)  # type: ignore
    return session


def _wrap_request_with_timeout(func, timeout: int):
    def _wrapped(method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return func(method, url, **kwargs)

    return _wrapped


def resolve_filters(args) -> dict:
    zones = args.zones or parse_env_list("NWS_ZONES") or DEFAULT_ZONES
    area = args.area or os.getenv("NWS_AREA")
    point = args.point or os.getenv("NWS_POINT")
    bbox = args.bbox or os.getenv("NWS_BBOX")
    statuses = args.status or parse_env_list("NWS_STATUS") or DEFAULT_STATUSES
    message_types = args.message_type or parse_env_list("NWS_MESSAGE_TYPES") or DEFAULT_MESSAGE_TYPES
    return {
        "zones": zones,
        "area": area,
        "point": point,
        "bbox": bbox,
        "statuses": statuses,
        "message_types": message_types,
    }


def build_param_sets(filters: dict, max_age_hours: int) -> List[dict]:
    base: dict = {
        "status": ",".join(filters["statuses"]),
        "message_type": ",".join(filters["message_types"]),
    }
    zones = filters.get("zones") or []
    if zones:
        params = []
        for zone in zones:
            entry = dict(base)
            entry.pop("area", None)
            entry.pop("point", None)
            entry.pop("bbox", None)
            entry["zone"] = zone
        params.append(entry)
        return params or [base]

    if filters.get("area"):
        base["area"] = filters["area"]
    if filters.get("point"):
        base["point"] = filters["point"]
    if filters.get("bbox"):
        base["bbox"] = filters["bbox"]
    return [base]


def fetch_alerts(session: requests.Session, param_sets: List[dict]) -> List[dict]:
    alerts: List[dict] = []
    seen_ids: set[str] = set()
    for params in param_sets:
        try:
            query: List[tuple[str, str]] = []
            for key, value in params.items():
                if key == "zone" and isinstance(value, list):
                    for item in value:
                        query.append((key, item))
                elif value is not None:
                    query.append((key, value))
            resp = session.get(BASE_URL, params=query)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("NWS fetch failed for params=%s: %s", params, exc)
            continue

        for feat in data.get("features", []):
            feat_id = feat.get("id") or feat.get("properties", {}).get("id")
            if feat_id and feat_id in seen_ids:
                continue
            if feat_id:
                seen_ids.add(feat_id)
            alerts.append(feat)
    return alerts


async def _get_pool(db_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(db_url, min_size=1, max_size=5)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest NWS active alerts")
    parser.add_argument("--zone", action="append", dest="zones", help="Zone ID (e.g., VAZ022)")
    parser.add_argument("--area", help="NWS area designator (e.g., VA)")
    parser.add_argument("--point", help="lat,long coordinate, e.g. 36.85,-81.5")
    parser.add_argument("--bbox", help="Bounding box minLon,minLat,maxLon,maxLat")
    parser.add_argument("--status", action="append", help="Status filter (actual, exercise, etc.)")
    parser.add_argument("--message-type", action="append", help="Message type (alert, update, cancel)")
    parser.add_argument("--max-age-hours", type=int, default=48, help="Limit alerts newer than N hours (default: 48)")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout per request (seconds)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    zones = args.zones or []
    if not zones:
        # Smyth (VAZ022), Washington (VAZ023), Wythe (VAZ024) typical AFO RNK examples
        zones = ["VAZ022", "VAZ023", "VAZ024"]

    filters = resolve_filters(args)
    session = build_session(os.getenv("NWS_USER_AGENT", "news-analyzer-osint/0.1"), args.timeout)
    param_sets = build_param_sets(filters, args.max_age_hours)
    alerts = fetch_alerts(session, param_sets)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL is required for nws_ingest")
    pool = await _get_pool(db_url)

    try:
        new_count = 0
        for feat in alerts:
            props = feat.get("properties", {})
            title = props.get("headline") or props.get("event") or "NWS Alert"
            url = props.get("@id") or feat.get("id")
            issued = props.get("onset") or props.get("effective") or props.get("sent")
            expires = props.get("expires") or props.get("ends")
            dt = datetime.now(timezone.utc)
            try:
                if issued:
                    dt = datetime.fromisoformat(issued.replace("Z", "+00:00"))
            except Exception:
                pass

            lines = []
            if props.get("event"):
                lines.append(f"Event: {props['event']}")
            if props.get("areaDesc"):
                lines.append(f"Area: {props['areaDesc']}")
            impact_bits = [
                f"Severity: {props.get('severity')}" if props.get("severity") else None,
                f"Urgency: {props.get('urgency')}" if props.get("urgency") else None,
                f"Certainty: {props.get('certainty')}" if props.get("certainty") else None,
            ]
            impact_bits = [bit for bit in impact_bits if bit]
            if impact_bits:
                lines.append("; ".join(impact_bits))
            if issued:
                lines.append(f"Issued: {issued}")
            if expires:
                lines.append(f"Expires: {expires}")

            desc = (props.get("description") or "").strip()
            instruction = (props.get("instruction") or "").strip()
            if desc:
                lines.extend(["", desc])
            if instruction:
                lines.extend(["", f"Instructions: {instruction}"])
            body = "\n".join(lines).strip()

            ch = md5((title or "") + body + (url or ""))
            metadata = {
                "severity": props.get("severity"),
                "urgency": props.get("urgency"),
                "certainty": props.get("certainty"),
                "zones": props.get("affectedZones"),
                "event": props.get("event"),
            }
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
                    body,
                    ch,
                    url,
                    "osint",
                    url,
                    "NWS Alerts",
                    "NWS",
                    None,
                    len(body.split()),
                    dt,
                    json.dumps(metadata),
                )
                new_count += 1

        if new_count:
            logger.info("Stored %d NWS alerts", new_count)
        else:
            logger.info("No NWS alerts")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
