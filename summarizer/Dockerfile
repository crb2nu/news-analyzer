# Multi-stage build for the news analyzer summarizer
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install Poetry
RUN pip install poetry

# Configure Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Copy poetry files
COPY summarizer/pyproject.toml summarizer/poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.in-project true && \
    poetry install --only=main --no-interaction --no-ansi --no-root && \
    rm -rf $POETRY_CACHE_DIR

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
COPY summarizer/*.py ./summarizer/
COPY summarizer/pyproject.toml ./

# Create non-root user
RUN groupadd -r summarizer && useradd -r -g summarizer summarizer
RUN chown -R summarizer:summarizer /app
USER summarizer

# Expose port for API
EXPOSE 8000

# Default command
CMD ["python", "-m", "summarizer.api"]