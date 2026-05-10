# syntax=docker/dockerfile:1.4
# FaithTracker Backend Dockerfile
# Litestar with Python 3.12
#
# PERFORMANCE: Uses BuildKit cache mounts for faster rebuilds
# Build command: DOCKER_BUILDKIT=1 docker compose build backend

FROM python:3.12-slim

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

# Create non-root user BEFORE copying code so file ownership is correct.
# UID 1001 is fixed so the host bind-mount (./data/uploads) can be chowned to
# match. Deployment note: run `sudo chown -R 1001:1001 ./data/uploads` (and
# any other writable bind mounts) on the host before `docker compose up`.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --no-create-home --shell /usr/sbin/nologin app

# Copy application code with correct ownership
COPY --chown=app:app . .

# Create uploads directory owned by app user
RUN mkdir -p /app/uploads /app/user_photos \
    && chown -R app:app /app/uploads /app/user_photos \
    && chmod 755 /app/uploads /app/user_photos

# Drop privileges — request handling, scheduler, file uploads all run as UID 1001.
USER app

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
