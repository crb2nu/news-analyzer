import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple, List

THINK_TAG_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class ModelFailover:
    """Track preferred/fallback model ordering with sticky success."""

    def __init__(self, primary: str, fallbacks: Sequence[str] | None = None) -> None:
        candidates: List[str] = []
        for name in [primary, *(fallbacks or [])]:
            if name and name not in candidates:
                candidates.append(name)
        if not candidates:
            raise ValueError("At least one model must be provided")
        self._candidates = candidates
        self._primary = candidates[0]
        self._active: Optional[str] = None

    @property
    def candidates(self) -> List[str]:
        return list(self._candidates)

    @property
    def current(self) -> str:
        return self._active or self._primary

    def iteration_order(self) -> List[str]:
        if self._active and self._active in self._candidates:
            ordered = [self._active] + [m for m in self._candidates if m != self._active]
            return ordered
        return list(self._candidates)

    def record_success(self, model: str) -> None:
        if model in self._candidates:
            self._active = model

    def mark_unavailable(self, model: str) -> None:
        if model == self._active:
            self._active = None


def is_invalid_model_error(exc: Exception) -> bool:
    """Detect LiteLLM invalid-model errors regardless of structure."""
    message = getattr(exc, "message", "") or str(exc)
    return "invalid model name" in message.lower()


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


async def chat_with_json_fallback(
    client: Any,
    model: str,
    messages: List[Dict[str, Any]],
    max_tokens: int,
    temperature: float = 0.3,
) -> Tuple[str, int]:
    """Attempt a JSON-mode chat call, then fall back to text mode.

    Some backends behind LiteLLM (e.g., certain vLLM models) do not support
    OpenAI's `response_format={"type":"json_object"}`. This helper first tries
    JSON mode and on error falls back to a regular chat completion.

    Returns a tuple of (content, total_tokens).
    """
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    except Exception:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    content = getattr(resp.choices[0].message, "content", "") or ""
    usage = getattr(resp, "usage", None)
    total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
    return content, int(total_tokens or 0)


def derive_fallback_title(
    title: Optional[str],
    content: Optional[str],
    source_path: Optional[str],
    page_number: Optional[int] = None,
) -> str:
    """Generate a reasonable title when the stored one is missing."""
    if title:
        cleaned = title.strip()
        if cleaned and not cleaned.lower().startswith("untitled"):
            return cleaned

    if content:
        for line in content.split("\n"):
            line = line.strip()
            if len(line.split()) >= 3:
                snippet = line[:200]
                return snippet + ("..." if len(line) > len(snippet) else "")

    if page_number:
        return f"Page {page_number}"

    if source_path:
        name = Path(source_path).name or source_path
        match = re.search(r"page_(\d+)", name, re.IGNORECASE)
        if match:
            return f"Page {int(match.group(1))}"
        pretty = name.replace('_', ' ').replace('-', ' ').strip()
        if pretty:
            return pretty.title()[:200]

    return "Untitled Article"
