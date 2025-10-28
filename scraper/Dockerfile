# Multi-stage build for the news analyzer scraper
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    # Dependencies for Playwright browsers
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxss1 \
    libasound2 \
    # Extra for Firefox/GTK headless
    libgtk-3-0 \
    libxcb-shm0 \
    libx11-xcb1 \
    libgdk-pixbuf-2.0-0 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libcairo-gobject2 \
    libfreetype6 \
    libfontconfig1 \
    libxcursor1 \
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
RUN poetry config virtualenvs.in-project true && \
    poetry install --only=main --no-interaction --no-ansi && \
    rm -rf $POETRY_CACHE_DIR

# Install Playwright browsers (chromium + firefox for stability)
RUN /app/.venv/bin/playwright install chromium firefox && \
    /app/.venv/bin/playwright install-deps chromium firefox

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Install runtime dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxss1 \
    libasound2 \
    libgtk-3-0 \
    libxcb-shm0 \
    libx11-xcb1 \
    libgdk-pixbuf-2.0-0 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libcairo-gobject2 \
    libfreetype6 \
    libfontconfig1 \
    libxcursor1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with home directory for Playwright
RUN groupadd -r scraper && \
    useradd -r -g scraper -d /home/scraper -m scraper

WORKDIR /app

# Copy virtual environment from base stage
COPY --from=base /app/.venv /app/.venv

# Copy Playwright browsers from base stage
COPY --from=base /root/.cache/ms-playwright /home/scraper/.cache/ms-playwright

# Copy application code into a package directory
COPY . /app/scraper

# Create storage directory for session state
RUN mkdir -p /app/storage

# Set proper permissions
RUN chown -R scraper:scraper /app /home/scraper

USER scraper

# Default command
CMD ["python", "-m", "scraper.downloader", "--help"]
