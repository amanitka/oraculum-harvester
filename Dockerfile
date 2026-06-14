# Stage 1: Build stage to install dependencies
FROM python:3.14-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation and caching
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first (for docker layer caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Final runtime stage
FROM python:3.14-slim

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy the rest of the application
COPY . /app

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create a non-root user and set permissions for data directories
RUN useradd -u 10001 -m appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

USER appuser

# Set working directory
WORKDIR /app

# Volume for persistent data (parquet exports, etc.)
VOLUME ["/app/data"]

# Entrypoint for the harvester service
ENTRYPOINT ["python", "-m", "harvester"]
