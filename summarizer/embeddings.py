from __future__ import annotations

import os
import asyncio
from typing import List, Optional

try:
    from openai import AsyncOpenAI
except Exception:
    AsyncOpenAI = None  # type: ignore

_local_model = None


async def embed_openai(texts: List[str], api_key: str, base_url: Optional[str], model: str) -> List[List[float]]:
    if not AsyncOpenAI:
        raise RuntimeError("openai client unavailable")
    default_headers = {"X-API-KEY": api_key}  # helps with LiteLLM setups that expect X-API-KEY
    client = AsyncOpenAI(api_key=api_key, base_url=base_url.rstrip('/') if base_url else None, default_headers=default_headers)
    resp = await client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


def _load_local_model(name: str):
    global _local_model
    if _local_model is not None:
        return _local_model
    from sentence_transformers import SentenceTransformer
    _local_model = SentenceTransformer(name)
    return _local_model


async def embed_local(texts: List[str], model_name: str = "BAAI/bge-small-en-v1.5") -> List[List[float]]:
    loop = asyncio.get_event_loop()
    model = _load_local_model(model_name)
    def _run():
        # Normalize embeddings for cosine similarity consumers
        embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embs.tolist()
    return await loop.run_in_executor(None, _run)


async def embed_with_fallback(texts: List[str]) -> List[List[float]]:
    """Try LiteLLM/OpenAI first; fall back to local on failure if enabled."""
    api_key = os.getenv('OPENAI_API_KEY') or ''
    base_url = os.getenv('OPENAI_API_BASE') or os.getenv('OPENAI_EMBED_BASE')
    model = os.getenv('OPENAI_EMBED_MODEL', 'text-embedding-3-small')
    enable_local = os.getenv('ENABLE_LOCAL_EMBED', 'false').lower() == 'true'
    local_name = os.getenv('LOCAL_EMBED_MODEL', 'BAAI/bge-small-en-v1.5')

    # Try OpenAI-compatible endpoint
    if api_key and base_url:
        try:
            return await embed_openai(texts, api_key, base_url, model)
        except Exception:
            if not enable_local:
                raise
    elif not enable_local:
        raise RuntimeError('No embedding backend configured')

    # Local fallback
    return await embed_local(texts, local_name)
