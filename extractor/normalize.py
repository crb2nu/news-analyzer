"""Normalization helpers for extractor layer.

Standardizes common free-form fields (e.g., section names) so that
downstream systems (feed UI, summaries, notifications) are consistent.
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
    """Normalize a section label to a canonical title.

    Returns "General" for empty/unknown values; preserves custom names
    when no alias mapping is found.
    """
    if not section:
        return "General"
    key = str(section).strip().lower()
    normalized = SECTION_ALIASES.get(key)
    if normalized:
        return normalized
    # Title-case simple sections, collapse whitespace
    cleaned = " ".join(section.split())
    # Avoid title-casing mixed alphanumerics (e.g., "A1") which should stay as-is
    return cleaned.title() if not cleaned.replace(" ", "").isdigit() else cleaned

