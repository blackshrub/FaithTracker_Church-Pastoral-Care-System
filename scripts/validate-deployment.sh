#!/bin/bash
# ===========================================
# FaithTracker Deployment Validation Script
# ===========================================
# Validates that all services are running correctly after deployment
# Run this after docker-compose up to verify the deployment
#
# Usage:
#   ./scripts/validate-deployment.sh
#   ./scripts/validate-deployment.sh --local    # Test against localhost only
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TIMEOUT=30

# Load environment variables
if [ -f "${PROJECT_DIR}/.env" ]; then
    source "${PROJECT_DIR}/.env"
fi

DOMAIN="${DOMAIN:-localhost}"
API_URL="https://api.${DOMAIN}"
FRONTEND_URL="https://${DOMAIN}"

# For local testing
if [ "$1" == "--local" ]; then
    API_URL="http://localhost:8001"
    FRONTEND_URL="http://localhost:8080"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0
WARNINGS=0

log_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_check() {
    echo -n "  ⏳ $1... "
}

log_pass() {
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASSED++))
}

log_fail() {
    echo -e "${RED}✗ FAIL${NC}"
    if [ -n "$1" ]; then
        echo -e "     ${RED}→ $1${NC}"
    fi
    ((FAILED++))
}

log_warn() {
    echo -e "${YELLOW}⚠ WARN${NC}"
    if [ -n "$1" ]; then
        echo -e "     ${YELLOW}→ $1${NC}"
    fi
    ((WARNINGS++))
}

# ===========================================
# Angie Web Server Checks (Host-level)
# ===========================================
check_angie() {
    log_header "Angie Web Server (Host-level)"

    log_check "Angie service status"
    if systemctl is-active --quiet angie 2>/dev/null; then
        log_pass
    else
        log_fail "Angie is not running. Run: sudo systemctl start angie"
    fi

    log_check "Angie configuration syntax"
    if angie -t 2>/dev/null; then
        log_pass
    else
        log_warn "Could not test config (may need sudo)"
    fi

    log_check "Angie listening on port 80"
    if netstat -tlnp 2>/dev/null | grep -q ":80 " || ss -tlnp 2>/dev/null | grep -q ":80 "; then
        log_pass
    else
        log_warn "Port 80 not detected"
    fi

    log_check "Angie listening on port 443"
    if netstat -tlnp 2>/dev/null | grep -q ":443 " || ss -tlnp 2>/dev/null | grep -q ":443 "; then
        log_pass
    else
        log_warn "Port 443 not detected"
    fi
}

# ===========================================
# Docker Container Checks
# ===========================================
check_docker_containers() {
    log_header "Docker Container Status"

    # Check if containers are running
    for container in faithtracker-mongo faithtracker-backend faithtracker-frontend; do
        log_check "Container ${container}"
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            STATUS=$(docker inspect --format='{{.State.Status}}' ${container})
            if [ "$STATUS" == "running" ]; then
                log_pass
            else
                log_fail "Status: ${STATUS}"
            fi
        else
            log_fail "Container not found"
        fi
    done

    # Check container health
    log_check "Backend container health"
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' faithtracker-backend 2>/dev/null || echo "unknown")
    if [ "$HEALTH" == "healthy" ]; then
        log_pass
    elif [ "$HEALTH" == "starting" ]; then
        log_warn "Container still starting"
    else
        log_fail "Health: ${HEALTH}"
    fi

    log_check "MongoDB container health"
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' faithtracker-mongo 2>/dev/null || echo "unknown")
    if [ "$HEALTH" == "healthy" ]; then
        log_pass
    elif [ "$HEALTH" == "starting" ]; then
        log_warn "Container still starting"
    else
        log_fail "Health: ${HEALTH}"
    fi
}

# ===========================================
# Local Service Checks (via localhost)
# ===========================================
check_local_services() {
    log_header "Local Service Health (Direct)"

    log_check "Backend on localhost:8001"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time ${TIMEOUT} "http://127.0.0.1:8001/health" 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        log_pass
    else
        log_fail "HTTP ${RESPONSE}"
    fi

    log_check "Frontend on localhost:8080"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time ${TIMEOUT} "http://127.0.0.1:8080/health" 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        log_pass
    else
        log_fail "HTTP ${RESPONSE}"
    fi
}

# ===========================================
# API Health Checks (via Angie)
# ===========================================
check_api_health() {
    log_header "API Health Checks (via Angie)"

    log_check "API health endpoint"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time ${TIMEOUT} "${API_URL}/health" 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        log_pass
    else
        log_fail "HTTP ${RESPONSE}"
    fi

    log_check "API readiness endpoint"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time ${TIMEOUT} "${API_URL}/ready" 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        log_pass
    else
        log_fail "HTTP ${RESPONSE}"
    fi

    log_check "Database connectivity (via /health)"
    BODY=$(curl -s --max-time ${TIMEOUT} "${API_URL}/health" 2>/dev/null || echo "{}")
    if echo "$BODY" | grep -q '"database":"connected"'; then
        log_pass
    else
        log_fail "Database not connected"
    fi

    log_check "API documentation (Swagger)"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time ${TIMEOUT} "${API_URL}/docs" 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        log_pass
    else
        log_warn "HTTP ${RESPONSE} - Swagger UI may be disabled"
    fi
}

# ===========================================
# Frontend Checks
# ===========================================
check_frontend() {
    log_header "Frontend Checks (via Angie)"

    log_check "Frontend accessible"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time ${TIMEOUT} "${FRONTEND_URL}" 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        log_pass
    elif [ "$RESPONSE" == "301" ] || [ "$RESPONSE" == "302" ]; then
        log_pass  # Redirect is OK
    else
        log_fail "HTTP ${RESPONSE}"
    fi

    log_check "Frontend health endpoint"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time ${TIMEOUT} "${FRONTEND_URL}/health" 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "200" ]; then
        log_pass
    else
        log_warn "HTTP ${RESPONSE}"
    fi
}

# ===========================================
# SSL/TLS Checks
# ===========================================
check_ssl() {
    log_header "SSL/TLS Checks"

    if [ "$1" == "--local" ]; then
        echo "  Skipping SSL checks for local environment"
        return
    fi

    log_check "SSL certificate valid"
    CERT_CHECK=$(echo | openssl s_client -servername "${DOMAIN}" -connect "${DOMAIN}:443" 2>/dev/null | openssl x509 -noout -checkend 86400 2>/dev/null && echo "valid" || echo "invalid")
    if [ "$CERT_CHECK" == "valid" ]; then
        log_pass
    else
        log_fail "Certificate expired or expiring within 24 hours"
    fi

    log_check "Certificate for api subdomain"
    CERT_CHECK=$(echo | openssl s_client -servername "api.${DOMAIN}" -connect "api.${DOMAIN}:443" 2>/dev/null | openssl x509 -noout -checkend 86400 2>/dev/null && echo "valid" || echo "invalid")
    if [ "$CERT_CHECK" == "valid" ]; then
        log_pass
    else
        log_fail "API certificate invalid"
    fi

    log_check "HTTPS redirect working"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time ${TIMEOUT} "http://${DOMAIN}" 2>/dev/null || echo "000")
    if [ "$RESPONSE" == "301" ] || [ "$RESPONSE" == "302" ] || [ "$RESPONSE" == "308" ]; then
        log_pass
    else
        log_warn "HTTP ${RESPONSE} - Expected redirect"
    fi
}

# ===========================================
# Security Headers Check
# ===========================================
check_security_headers() {
    log_header "Security Headers"

    HEADERS=$(curl -s -I --max-time ${TIMEOUT} "${API_URL}/health" 2>/dev/null || echo "")

    log_check "Strict-Transport-Security (HSTS)"
    if echo "$HEADERS" | grep -qi "strict-transport-security"; then
        log_pass
    else
        log_warn "Header not found"
    fi

    log_check "X-Frame-Options header"
    if echo "$HEADERS" | grep -qi "x-frame-options"; then
        log_pass
    else
        log_warn "Header not found"
    fi

    log_check "X-Content-Type-Options header"
    if echo "$HEADERS" | grep -qi "x-content-type-options"; then
        log_pass
    else
        log_warn "Header not found"
    fi

    log_check "Referrer-Policy header"
    if echo "$HEADERS" | grep -qi "referrer-policy"; then
        log_pass
    else
        log_warn "Header not found"
    fi
}

# ===========================================
# Database Checks
# ===========================================
check_database() {
    log_header "Database Checks"

    log_check "MongoDB connection"
    if docker exec faithtracker-mongo mongosh --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        log_pass
    else
        log_fail "Cannot connect to MongoDB"
    fi

    log_check "Database indexes exist"
    INDEX_COUNT=$(docker exec faithtracker-mongo mongosh --quiet faithtracker --eval "db.members.getIndexes().length" 2>/dev/null || echo "0")
    if [ "$INDEX_COUNT" -gt "1" ]; then
        log_pass
    else
        log_warn "Limited indexes found (${INDEX_COUNT})"
    fi
}

# ===========================================
# Summary
# ===========================================
print_summary() {
    log_header "Validation Summary"
    echo ""
    echo -e "  ${GREEN}Passed:${NC}   ${PASSED}"
    echo -e "  ${RED}Failed:${NC}   ${FAILED}"
    echo -e "  ${YELLOW}Warnings:${NC} ${WARNINGS}"
    echo ""

    if [ ${FAILED} -eq 0 ]; then
        echo -e "${GREEN}✓ All critical checks passed!${NC}"
        if [ ${WARNINGS} -gt 0 ]; then
            echo -e "${YELLOW}  (${WARNINGS} warnings - review recommended)${NC}"
        fi
        return 0
    else
        echo -e "${RED}✗ ${FAILED} critical check(s) failed!${NC}"
        echo -e "${RED}  Please review the errors above and fix before production use.${NC}"
        return 1
    fi
}

# ===========================================
# Main
# ===========================================
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     FaithTracker Deployment Validation                     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Domain:   ${DOMAIN}"
    echo "  API URL:  ${API_URL}"
    echo "  Time:     $(date)"

    check_angie
    check_docker_containers
    check_local_services
    check_api_health
    check_frontend
    check_ssl "$1"
    check_security_headers
    check_database
    print_summary
}

main "$@"
