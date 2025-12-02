# FaithTracker Frontend Dockerfile
# Multi-stage build: Node for building, Nginx for serving
# Uses Vite + SWC for ultra-fast builds
# Optimized with BuildKit cache mounts

# syntax=docker/dockerfile:1.4

# ===================
# Stage 1: Dependencies
# ===================
# Try to use pre-built base image, fall back to node:20-alpine
ARG BASE_IMAGE=node:20-alpine
FROM ${BASE_IMAGE} AS deps

WORKDIR /app

# Disable telemetry
ENV YARN_ENABLE_TELEMETRY=0

# Copy package files
COPY package.json yarn.lock ./

# Install dependencies with BuildKit cache mounts
# This caches node_modules and yarn cache between builds
RUN --mount=type=cache,target=/root/.yarn/berry/cache \
    --mount=type=cache,target=/app/node_modules,sharing=locked \
    yarn install --frozen-lockfile --network-timeout 600000 && \
    cp -r node_modules /tmp/node_modules

# ===================
# Stage 2: Build
# ===================
FROM node:20-alpine AS builder

WORKDIR /app

# Build argument for API URL (can be overridden at build time)
ARG VITE_BACKEND_URL=https://api.localhost
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
ENV NODE_ENV=production

# Copy cached node_modules from deps stage
COPY --from=deps /tmp/node_modules ./node_modules

# Copy package files (needed for scripts)
COPY package.json yarn.lock ./

# Copy source files
COPY index.html ./
COPY public ./public
COPY src ./src
COPY vite.config.js tailwind.config.js postcss.config.js ./

# Build the application with optimizations
RUN yarn build

# ===================
# Stage 3: Serve
# ===================
FROM nginx:alpine AS production

# Install wget for health checks
RUN apk add --no-cache wget

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
