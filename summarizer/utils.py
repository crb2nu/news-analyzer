import json
import re
from typing import Any, Dict, Tuple

THINK_TAG_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def sanitize_response_text(raw: str) -> str:
    """Remove litellm/vllm thinking annotations and trim whitespace."""
    if not raw:
        return ""
    cleaned = THINK_TAG_PATTERN.sub("", raw)
    return cleaned.strip()


def extract_json_object(raw: str) -> Tuple[Dict[str, Any], bool]:
    """Attempt to parse a JSON object from model output.

    Returns a tuple of (data, used_fallback). When parsing fails we synthesize
    a minimal structure out of the free-form text so downstream code can keep
    moving instead of erroring out.
    """
    cleaned = sanitize_response_text(raw)
    if not cleaned:
        return {
            "summary": "",
            "key_points": [],
            "sentiment": "neutral",
            "topics": [],
            "confidence_score": 0.5,
        }, True

    # First pass: direct JSON decode
    try:
        return json.loads(cleaned), False
    except json.JSONDecodeError:
        pass

    # Second pass: locate JSON substring within the content
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = cleaned[start : end + 1]
        try:
            return json.loads(snippet), True
        except json.JSONDecodeError:
            pass

    # Fallback: build a minimal structure from the text
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    bullets = [line.lstrip("-•* ") for line in lines if line[:1] in {"-", "•", "*"}]
    non_bullets = [line for line in lines if line not in bullets]
    summary_text = " ".join(non_bullets).strip() or cleaned
    return {
        "summary": summary_text,
        "key_points": bullets,
        "sentiment": "neutral",
        "topics": [],
        "confidence_score": 0.6,
    }, True
