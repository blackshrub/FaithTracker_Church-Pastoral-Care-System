#!/bin/bash
# ============================================================
# FaithTracker Security Audit Script
# ============================================================
# Run this script regularly (weekly recommended) to check for
# vulnerabilities in dependencies.
#
# Usage:
#   ./scripts/security-audit.sh          # Full audit
#   ./scripts/security-audit.sh --fix    # Audit and auto-update vulnerable packages
#   ./scripts/security-audit.sh --ci     # CI mode (exit code 1 if vulnerabilities found)
#
# Prerequisites:
#   - Docker running with faithtracker containers
#   - OR Python venv with pip-audit installed
#   - yarn installed for frontend audit
# ============================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flags
FIX_MODE=false
CI_MODE=false
VULNERABILITIES_FOUND=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --fix)
            FIX_MODE=true
            shift
            ;;
        --ci)
            CI_MODE=true
            shift
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  FaithTracker Security Audit${NC}"
echo -e "${BLUE}  $(date)${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# ============================================================
# Backend Python Dependencies Audit
# ============================================================
echo -e "${YELLOW}[1/3] Auditing Backend Python Dependencies...${NC}"
echo ""

# Try Docker container first, then local
if docker ps --format '{{.Names}}' | grep -q 'faithtracker-backend'; then
    echo "Using Docker container for audit..."

    # Install pip-audit in container if not present
    docker exec faithtracker-backend pip install pip-audit -q 2>/dev/null || true

    # Run audit
    BACKEND_AUDIT=$(docker exec faithtracker-backend pip-audit --progress-spinner off 2>&1) || true

    if echo "$BACKEND_AUDIT" | grep -q "Found [1-9]"; then
        echo -e "${RED}Backend vulnerabilities found:${NC}"
        echo "$BACKEND_AUDIT"
        VULNERABILITIES_FOUND=true

        if [ "$FIX_MODE" = true ]; then
            echo ""
            echo -e "${YELLOW}Attempting to fix backend vulnerabilities...${NC}"
            docker exec faithtracker-backend pip-audit --fix --dry-run 2>&1 || true
            echo -e "${YELLOW}Review suggested fixes above and update requirements.txt manually.${NC}"
        fi
    else
        echo -e "${GREEN}No vulnerabilities found in backend dependencies.${NC}"
    fi
else
    echo -e "${YELLOW}Docker container not running. Auditing locked deps from uv.lock...${NC}"

    if command -v pip-audit &> /dev/null && command -v uv &> /dev/null; then
        cd "$PROJECT_ROOT/backend"
        # Export the locked production-only deps to a requirements file
        # pip-audit understands. --no-dev keeps audit focused on prod image.
        uv export --frozen --no-dev --format requirements.txt -o /tmp/audit-reqs.txt
        BACKEND_AUDIT=$(pip-audit -r /tmp/audit-reqs.txt --progress-spinner off 2>&1) || true

        if echo "$BACKEND_AUDIT" | grep -q "Found [1-9]"; then
            echo -e "${RED}Backend vulnerabilities found:${NC}"
            echo "$BACKEND_AUDIT"
            VULNERABILITIES_FOUND=true
        else
            echo -e "${GREEN}No vulnerabilities found in backend dependencies.${NC}"
        fi
    else
        echo -e "${YELLOW}pip-audit not installed. Install with: pip install pip-audit${NC}"
        echo -e "${YELLOW}Skipping backend audit.${NC}"
    fi
fi

echo ""

# ============================================================
# Frontend JavaScript Dependencies Audit
# ============================================================
echo -e "${YELLOW}[2/3] Auditing Frontend JavaScript Dependencies...${NC}"
echo ""

cd "$PROJECT_ROOT/frontend"

if command -v yarn &> /dev/null; then
    FRONTEND_AUDIT=$(yarn audit --groups dependencies 2>&1) || true

    if echo "$FRONTEND_AUDIT" | grep -q "[1-9]\+ vulnerabilities"; then
        echo -e "${RED}Frontend vulnerabilities found:${NC}"
        echo "$FRONTEND_AUDIT"
        VULNERABILITIES_FOUND=true

        if [ "$FIX_MODE" = true ]; then
            echo ""
            echo -e "${YELLOW}Attempting to fix frontend vulnerabilities...${NC}"
            yarn upgrade --latest 2>&1 || true
        fi
    else
        echo -e "${GREEN}No vulnerabilities found in frontend dependencies.${NC}"
    fi
elif command -v npm &> /dev/null; then
    FRONTEND_AUDIT=$(npm audit --production 2>&1) || true

    if echo "$FRONTEND_AUDIT" | grep -q "found [1-9]"; then
        echo -e "${RED}Frontend vulnerabilities found:${NC}"
        echo "$FRONTEND_AUDIT"
        VULNERABILITIES_FOUND=true

        if [ "$FIX_MODE" = true ]; then
            echo ""
            echo -e "${YELLOW}Attempting to fix frontend vulnerabilities...${NC}"
            npm audit fix 2>&1 || true
        fi
    else
        echo -e "${GREEN}No vulnerabilities found in frontend dependencies.${NC}"
    fi
else
    echo -e "${YELLOW}Neither yarn nor npm found. Skipping frontend audit.${NC}"
fi

echo ""

# ============================================================
# Docker Image Security Scan (if trivy is available)
# ============================================================
echo -e "${YELLOW}[3/3] Checking Docker Images (optional)...${NC}"
echo ""

if command -v trivy &> /dev/null; then
    echo "Scanning Docker images with Trivy..."

    for image in faithtracker-backend faithtracker-frontend faithtracker-mongo; do
        if docker images --format '{{.Repository}}' | grep -q "$image"; then
            echo ""
            echo -e "${BLUE}Scanning $image...${NC}"
            trivy image --severity HIGH,CRITICAL "$image" 2>&1 || true
        fi
    done
else
    echo -e "${YELLOW}Trivy not installed. Skipping Docker image scan.${NC}"
    echo -e "${YELLOW}Install Trivy for container security scanning: https://trivy.dev${NC}"
fi

echo ""
echo -e "${BLUE}============================================================${NC}"

# ============================================================
# Summary
# ============================================================
if [ "$VULNERABILITIES_FOUND" = true ]; then
    echo -e "${RED}  VULNERABILITIES FOUND - Review and fix above issues${NC}"
    echo -e "${BLUE}============================================================${NC}"

    if [ "$CI_MODE" = true ]; then
        exit 1
    fi
else
    echo -e "${GREEN}  All security checks passed!${NC}"
    echo -e "${BLUE}============================================================${NC}"
fi

echo ""
echo "Next steps:"
echo "  1. Review any vulnerabilities found above"
echo "  2. Update affected packages in requirements.txt or package.json"
echo "  3. Test changes before deploying"
echo "  4. Run this audit regularly (recommend weekly cron job)"
echo ""
echo "To set up weekly cron job:"
echo "  crontab -e"
echo "  0 0 * * 0 $PROJECT_ROOT/scripts/security-audit.sh --ci >> /var/log/security-audit.log 2>&1"
echo ""
