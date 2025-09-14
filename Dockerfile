# Multi-stage build for all components

# ===== SCRAPER =====
FROM python:3.11-slim AS scraper
WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install poetry==1.8.5
COPY scraper/pyproject.toml scraper/poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi
COPY scraper/ ./
CMD ["python", "-m", "scraper"]

# ===== EXTRACTOR =====
FROM python:3.11-slim AS extractor
WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install poetry==1.8.5
COPY extractor/pyproject.toml extractor/poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi
COPY extractor/ ./
CMD ["python", "-m", "extractor"]

# ===== SUMMARIZER =====
FROM python:3.11-slim AS summarizer
WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install poetry==1.8.5
COPY summarizer/pyproject.toml summarizer/poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi
COPY summarizer/ ./
CMD ["python", "-m", "summarizer"]

# ===== NOTIFIER =====
FROM python:3.11-slim AS notifier
WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install poetry==1.8.5
COPY notifier/pyproject.toml notifier/poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi
COPY notifier/ ./
CMD ["python", "-m", "notifier"]