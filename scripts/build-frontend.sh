#!/bin/bash
# Fast Frontend Build Script
# Builds frontend in ~25 seconds instead of 5-7 minutes
#
# Usage:
#   ./scripts/build-frontend.sh          # Fast build (code changes only)
#   ./scripts/build-frontend.sh --deps   # Rebuild dependencies (when package.json changes)
#   ./scripts/build-frontend.sh --full   # Full rebuild (same as docker compose build)

set -e

cd "$(dirname "$0")/.."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get VITE_BACKEND_URL from .env or docker-compose.yml
if [ -f .env ]; then
    # Extract DOMAIN safely (handles values with spaces)
    DOMAIN=$(grep -E "^DOMAIN=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    if [ -n "$DOMAIN" ]; then
        BACKEND_URL="https://api.${DOMAIN}"
    else
        BACKEND_URL="https://api.localhost"
    fi
else
    BACKEND_URL="https://api.localhost"
fi

case "${1:-}" in
    --deps)
        echo -e "${YELLOW}Building dependencies image (run when package.json changes)...${NC}"
        cd frontend
        time docker build -f Dockerfile.deps -t faithtracker-frontend-deps .
        echo -e "${GREEN}Dependencies image built! Now run without --deps for fast builds.${NC}"
        ;;
    --full)
        echo -e "${YELLOW}Running full build (slow)...${NC}"
        time docker compose build --no-cache frontend
        docker compose up -d frontend
        echo -e "${GREEN}Full build complete!${NC}"
        ;;
    *)
        # Check if deps image exists
        if ! docker image inspect faithtracker-frontend-deps >/dev/null 2>&1; then
            echo -e "${YELLOW}Dependencies image not found. Building it first (one-time)...${NC}"
            cd frontend
            docker build -f Dockerfile.deps -t faithtracker-frontend-deps .
            cd ..
        fi

        echo -e "${GREEN}Fast build (code changes only)...${NC}"
        cd frontend
        time docker build -f Dockerfile.fast \
            -t faithtracker_church-pastoral-care-system-frontend \
            --build-arg VITE_BACKEND_URL="$BACKEND_URL" \
            .
        cd ..

        echo -e "${GREEN}Restarting frontend container...${NC}"
        docker compose up -d frontend

        echo -e "${GREEN}Done! Frontend rebuilt and deployed.${NC}"
        ;;
esac
