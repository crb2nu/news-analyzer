# Multi-stage build for the news analyzer notifier
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Configure Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --only=main && rm -rf $POETRY_CACHE_DIR

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment from base stage
COPY --from=base /app/.venv /app/.venv

# Copy application code
COPY notifier/ ./notifier/
COPY extractor/database.py ./extractor/database.py
COPY extractor/__init__.py ./extractor/__init__.py
COPY scraper/config.py ./scraper/config.py
COPY scraper/__init__.py ./scraper/__init__.py
COPY pyproject.toml ./

# Create templates directory
RUN mkdir -p /app/notifier/templates

# Create non-root user
RUN groupadd -r notifier && useradd -r -g notifier notifier
RUN chown -R notifier:notifier /app
USER notifier

# Default command
CMD ["python", "-m", "notifier.service", "--help"]