# syntax=docker/dockerfile:1.4
# FaithTracker Backend Dockerfile
# FastAPI with Python 3.11
#
# PERFORMANCE: Uses BuildKit cache mounts for faster rebuilds
# Build command: DOCKER_BUILDKIT=1 docker compose build backend

FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Jakarta

# Set working directory
WORKDIR /app

# Install system dependencies (including WeasyPrint dependencies for PDF generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    curl \
    tzdata \
    # WeasyPrint dependencies for PDF generation
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

# Use Aliyun PyPI mirror for Indonesia (300x faster than default PyPI)
# Default PyPI routes through US->Europe->Indonesia at ~45 KB/s
# Aliyun routes directly to Asia at ~13 MB/s
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with BuildKit cache mount
# Cache persists across builds for ~5x faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads && chmod 755 /app/uploads

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application with Granian (Rust-based ASGI server - faster than Uvicorn)
# --workers: Number of worker processes
# --interface asgi: ASGI protocol for FastAPI
# --http auto: Auto-negotiate HTTP/1.1 or HTTP/2 (H2C upgrade)
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--http", "auto", "server:app"]
