ARG PYTHON_BASE=registry.harbor.lan/dockerhub-cache/library/python:3.11-slim

FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Copy frontend source
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./

# Build static site
ENV PUBLIC_API_BASE_URL=""
RUN npm run build

# Python application stage
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
COPY summarizer/pyproject.toml summarizer/poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry lock --no-update \
    && poetry install --no-interaction --no-ansi

# Copy application code
COPY summarizer/ .

# Copy built frontend from previous stage
COPY --from=frontend-builder /frontend/build ./static/ui

# Expose port
EXPOSE 8000

# Run the FastAPI app by default
CMD ["python", "-m", "api"]
