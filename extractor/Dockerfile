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
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy application code
COPY . .

# Run the application
# Run the processor as the default entrypoint
CMD ["python", "-m", "processor"]
