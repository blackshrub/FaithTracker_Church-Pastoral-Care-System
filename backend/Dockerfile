# syntax=docker/dockerfile:1.7
# FaithTracker Backend — Multi-stage Dockerfile
#
# PERFORMANCE NOTES:
# - Stage 1 ("deps") rarely changes. It rebuilds only when requirements.txt,
#   the apt package list, or the Python base image moves. ~2 min cold,
#   instant on cache hit.
# - Stage 2 ("runtime") rebuilds on every code change. ~5-10 s typical.
# - `uv` replaces `pip` for installs (10-100× faster wheel resolution +
#   parallel downloads).
# - BuildKit cache mounts persist apt + uv caches across builds.
#
# Build:  DOCKER_BUILDKIT=1 docker compose build backend
# Force-rebuild deps: docker compose build --no-cache backend (or bump
# requirements.txt — the deps layer key is its hash).

# =============================================================================
# Stage 1: deps — system libs + Python wheels (cacheable, slow-changing)
# =============================================================================
FROM python:3.12-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # uv: parallel + Rust-resolved installer
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

WORKDIR /app

# System libraries. WeasyPrint needs the full pango/cairo/gdk-pixbuf stack
# for PDF rendering. Cache mount on /var/cache/apt avoids re-downloading on
# subsequent rebuilds (the apt-get clean at the end is gone deliberately —
# the cache mount handles that across builds).
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && apt-get install -y --no-install-recommends \
      gcc \
      libffi-dev \
      curl \
      tzdata \
      libpango-1.0-0 \
      libpangocairo-1.0-0 \
      libpangoft2-1.0-0 \
      libcairo2 \
      libgdk-pixbuf-2.0-0 \
      fonts-liberation \
      fonts-dejavu-core

# uv bootstrap (small ~10 MB binary install, no cache needed).
# HTTPS index — no PIP_TRUSTED_HOST; cert verification stays on.
RUN pip install --no-cache-dir uv

# Install Python deps with uv. The cache mount on /root/.cache/uv keeps
# downloaded wheels warm across builds, so even a deps-stage rebuild is
# 5-10× faster than the cold path. --system installs into the base
# interpreter (no venv) which keeps the runtime image simple.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

# =============================================================================
# Stage 2: runtime — code + non-root user (fast-changing)
# =============================================================================
FROM deps AS runtime

ENV TZ=Asia/Jakarta

# Timezone + non-root user (UID 1001 fixed so host bind-mounts can match).
# Deployment note: `sudo chown -R 1001:1001 ./data/uploads` once before
# `docker compose up` after upgrading.
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
 && groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --no-create-home --shell /usr/sbin/nologin app

# Copy application code with correct ownership
COPY --chown=app:app . .

# Create writable runtime dirs owned by app user
RUN mkdir -p /app/uploads /app/user_photos \
 && chown -R app:app /app/uploads /app/user_photos \
 && chmod 755 /app/uploads /app/user_photos

# Drop privileges — request handling, scheduler, file uploads all run as UID 1001.
USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Granian (Rust-based ASGI server). --workers env-driven via GRANIAN_WORKERS
# (default 2) so ops can tune without rebuilding. exec ensures granian is
# PID 1 for proper signal handling.
CMD ["sh", "-c", "exec granian --interface asgi --host 0.0.0.0 --port 8001 --workers ${GRANIAN_WORKERS:-2} --http auto server:app"]
