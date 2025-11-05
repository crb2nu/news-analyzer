"""Normalization helpers for scraper layer.

Keep this in sync with extractor/normalize.py so that section labels are
consistent at both discovery and write time.
"""

from typing import Optional

SECTION_ALIASES = {
    "obituary": "Obituaries",
    "obituaries": "Obituaries",
    "obits": "Obituaries",
    "sports": "Sports",
    "news": "News",
    "local": "Local",
    "business": "Business",
    "opinion": "Opinion",
    "editorial": "Opinion",
    "police": "Public Safety",
    "police and courts": "Public Safety",
    "crime": "Public Safety",
    "classifieds": "Classifieds",
}


def normalize_section(section: Optional[str]) -> Optional[str]:
    if not section:
        return None
    key = str(section).strip().lower()
    mapped = SECTION_ALIASES.get(key)
    if mapped:
        return mapped
    cleaned = " ".join(section.split())
    return cleaned.title() if not cleaned.replace(" ", "").isdigit() else cleaned

