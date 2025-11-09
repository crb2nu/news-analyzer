ARG PYTHON_BASE=registry.harbor.lan/dockerhub-cache/library/python:3.11-slim
FROM ${PYTHON_BASE}

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.8.5

# Copy dependency files
COPY notifier/pyproject.toml notifier/poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy application code into package directory
COPY notifier /app/notifier

# Expose packages on PYTHONPATH for module execution
ENV PYTHONPATH=/app

# Run the notifier module directly
CMD ["python", "-m", "notifier.ntfy_notifier"]
