#!/bin/bash
# ===========================================
# FaithTracker - SSL Certificate Setup
# ===========================================
# Obtains SSL certificates from Let's Encrypt using Certbot
#
# Usage:
#   sudo ./setup-ssl.sh
#
# Prerequisites:
#   - Angie installed (run install.sh first)
#   - DNS records pointing to this server
#   - DOMAIN and ACME_EMAIL set in .env

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root (sudo)"
        exit 1
    fi
}

load_env() {
    if [ -f "${PROJECT_DIR}/.env" ]; then
        set -a
        source "${PROJECT_DIR}/.env"
        set +a
        log_info "Loaded environment from .env"
    else
        log_error ".env file not found!"
        log_error "Please create .env with DOMAIN and ACME_EMAIL"
        exit 1
    fi

    if [ -z "$DOMAIN" ]; then
        log_error "DOMAIN not set in .env"
        exit 1
    fi

    if [ -z "$ACME_EMAIL" ]; then
        log_error "ACME_EMAIL not set in .env"
        exit 1
    fi

    log_info "Domain: $DOMAIN"
    log_info "Email: $ACME_EMAIL"
}

# ===================
# SSL Setup Steps
# ===================

check_dns() {
    log_step "Checking DNS records"

    # Check main domain
    RESOLVED_IP=$(dig +short "$DOMAIN" | head -n1)
    if [ -z "$RESOLVED_IP" ]; then
        log_error "DNS not configured for $DOMAIN"
        log_error "Please add an A record pointing to this server"
        exit 1
    fi
    log_info "$DOMAIN resolves to $RESOLVED_IP"

    # Check API subdomain
    API_IP=$(dig +short "api.$DOMAIN" | head -n1)
    if [ -z "$API_IP" ]; then
        log_error "DNS not configured for api.$DOMAIN"
        log_error "Please add an A record pointing to this server"
        exit 1
    fi
    log_info "api.$DOMAIN resolves to $API_IP"
}

create_temp_config() {
    log_step "Creating temporary HTTP config"

    # Create minimal HTTP-only config for ACME challenge
    cat > /etc/angie/conf.d/temp-acme.conf << EOF
# Temporary config for ACME challenge
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} api.${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        allow all;
    }

    location / {
        return 444;
    }
}
EOF

    # Disable main config temporarily if it exists
    if [ -f /etc/angie/conf.d/faithtracker.conf ]; then
        mv /etc/angie/conf.d/faithtracker.conf /etc/angie/conf.d/faithtracker.conf.disabled
    fi

    # Reload Angie
    systemctl reload angie
    log_info "Temporary config active"
}

obtain_certificates() {
    log_step "Obtaining SSL certificates"

    # Request certificates for both domains
    certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "$ACME_EMAIL" \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        -d "$DOMAIN" \
        -d "api.$DOMAIN"

    if [ $? -eq 0 ]; then
        log_info "Certificates obtained successfully"
    else
        log_error "Failed to obtain certificates"
        cleanup_temp_config
        exit 1
    fi
}

cleanup_temp_config() {
    log_step "Cleaning up temporary config"

    # Remove temporary config
    rm -f /etc/angie/conf.d/temp-acme.conf

    # Restore main config
    if [ -f /etc/angie/conf.d/faithtracker.conf.disabled ]; then
        mv /etc/angie/conf.d/faithtracker.conf.disabled /etc/angie/conf.d/faithtracker.conf
    fi

    log_info "Temporary config removed"
}

generate_final_config() {
    log_step "Generating final site configuration"

    # Generate config from template using envsubst
    envsubst '${DOMAIN}' < "${SCRIPT_DIR}/conf.d/faithtracker.conf.template" > /etc/angie/conf.d/faithtracker.conf

    log_info "Generated faithtracker.conf"
}

test_and_reload() {
    log_step "Testing and reloading Angie"

    if angie -t; then
        log_info "Configuration test passed"
        systemctl reload angie
        log_info "Angie reloaded"
    else
        log_error "Configuration test failed!"
        log_error "Check /etc/angie/conf.d/faithtracker.conf"
        exit 1
    fi
}

verify_ssl() {
    log_step "Verifying SSL configuration"

    # Wait for Angie to fully reload
    sleep 2

    # Check HTTPS is working
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "https://${DOMAIN}" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "502" ] || [ "$HTTP_CODE" = "503" ]; then
        log_warn "Got HTTP $HTTP_CODE - This is expected if Docker services aren't running"
        log_info "SSL certificate is working, but upstream (Docker) is not available"
    elif [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        log_info "SSL verified - HTTPS is working (HTTP $HTTP_CODE)"
    else
        log_warn "Got HTTP $HTTP_CODE when checking https://${DOMAIN}"
        log_warn "This may be normal if Docker services aren't running yet"
    fi

    # Show certificate info
    echo ""
    log_info "Certificate details:"
    echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | openssl x509 -noout -dates -subject 2>/dev/null || log_warn "Could not retrieve certificate info"
}

print_success() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     SSL Certificates Installed Successfully!              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Certificate location:"
    echo "  ${YELLOW}/etc/letsencrypt/live/${DOMAIN}/${NC}"
    echo ""
    echo "Your sites are now available at:"
    echo "  Frontend: ${GREEN}https://${DOMAIN}${NC}"
    echo "  API:      ${GREEN}https://api.${DOMAIN}${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start Docker services:"
    echo "     ${GREEN}docker compose up -d${NC}"
    echo ""
    echo "  2. Verify deployment:"
    echo "     ${GREEN}./scripts/validate-deployment.sh${NC}"
    echo ""
    echo "Certificate renewal is automatic via Certbot timer."
    echo "Check renewal status: ${YELLOW}systemctl status certbot.timer${NC}"
    echo ""
}

# ===================
# Main
# ===================

main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     FaithTracker - SSL Certificate Setup                   ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_root
    load_env
    check_dns
    create_temp_config
    obtain_certificates
    cleanup_temp_config
    generate_final_config
    test_and_reload
    verify_ssl
    print_success
}

main "$@"
