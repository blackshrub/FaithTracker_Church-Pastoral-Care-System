#!/bin/bash
# ===========================================
# FaithTracker - Generate Angie Configuration
# ===========================================
# Generates site configuration from template using .env variables
#
# Usage:
#   ./generate-config.sh           # Generate and copy to /etc/angie
#   ./generate-config.sh --dry-run # Show output without copying

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ===================
# Helper Functions
# ===================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ===================
# Main
# ===================

DRY_RUN=false
if [ "$1" = "--dry-run" ]; then
    DRY_RUN=true
fi

# Load environment variables
if [ -f "${PROJECT_DIR}/.env" ]; then
    set -a
    source "${PROJECT_DIR}/.env"
    set +a
else
    log_error ".env file not found!"
    exit 1
fi

# Check required variables
if [ -z "$DOMAIN" ]; then
    log_error "DOMAIN not set in .env"
    exit 1
fi

log_info "Generating configuration for domain: $DOMAIN"

# Generate config
TEMPLATE="${SCRIPT_DIR}/conf.d/faithtracker.conf.template"
OUTPUT="${SCRIPT_DIR}/conf.d/faithtracker.conf.generated"

if [ ! -f "$TEMPLATE" ]; then
    log_error "Template not found: $TEMPLATE"
    exit 1
fi

envsubst '${DOMAIN}' < "$TEMPLATE" > "$OUTPUT"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "Generated configuration (dry-run):"
    echo "=================================="
    cat "$OUTPUT"
    rm "$OUTPUT"
else
    log_info "Generated: $OUTPUT"

    # Copy to system if running as root
    if [ "$EUID" -eq 0 ]; then
        cp "$OUTPUT" /etc/angie/conf.d/faithtracker.conf
        log_info "Copied to /etc/angie/conf.d/faithtracker.conf"

        # Test configuration
        if angie -t 2>/dev/null; then
            log_info "Configuration test passed"
            echo ""
            echo "To apply changes, run:"
            echo "  ${YELLOW}sudo systemctl reload angie${NC}"
        else
            log_error "Configuration test failed!"
            angie -t
        fi
    else
        echo ""
        echo "To install the configuration, run:"
        echo "  ${YELLOW}sudo cp $OUTPUT /etc/angie/conf.d/faithtracker.conf${NC}"
        echo "  ${YELLOW}sudo angie -t${NC}"
        echo "  ${YELLOW}sudo systemctl reload angie${NC}"
    fi
fi
