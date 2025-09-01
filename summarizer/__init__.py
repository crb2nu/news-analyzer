"""
AI summarization service for news analyzer.

This module provides OpenAI-powered summarization of extracted articles
with support for batch processing, rate limiting, and token usage tracking.
"""

__version__ = "0.1.0"

# Import batch processing components if needed elsewhere
from .batch import (
    ArticleSummarizer,
    BatchProcessor,
    SummaryResponse,
)

__all__ = [
    "ArticleSummarizer",
    "BatchProcessor",
    "SummaryResponse",
]