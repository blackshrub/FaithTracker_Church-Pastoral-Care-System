#!/bin/bash
# ===========================================
# FaithTracker - Angie Installation Script
# ===========================================
# Installs Angie (nginx fork) with HTTP/3 and Brotli support
# Supports: Debian 10/11/12, Ubuntu 20.04/22.04/24.04
#
# Usage:
#   sudo ./install.sh
#
# This script will:
#   1. Add Angie APT repository
#   2. Install Angie with all modules
#   3. Install Certbot for SSL certificates
#   4. Create directory structure
#   5. Copy configuration files
#   6. Enable and start Angie

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

check_os() {
    if [ ! -f /etc/os-release ]; then
        log_error "Cannot detect OS. Only Debian/Ubuntu are supported."
        exit 1
    fi

    . /etc/os-release

    if [[ "$ID" != "debian" && "$ID" != "ubuntu" ]]; then
        log_error "Unsupported OS: $ID. Only Debian and Ubuntu are supported."
        exit 1
    fi

    OS_ID=$ID
    OS_VERSION=$VERSION_CODENAME
    log_info "Detected OS: $ID $VERSION_CODENAME"
}

# ===================
# Installation Steps
# ===================

install_dependencies() {
    log_step "Installing dependencies"

    apt-get update
    apt-get install -y \
        curl \
        gnupg2 \
        ca-certificates \
        lsb-release \
        gettext-base \
        cron

    log_info "Dependencies installed"
}

install_angie() {
    log_step "Installing Angie"

    # Add Angie signing key
    log_info "Adding Angie GPG key..."
    curl -fsSL https://angie.software/keys/angie-signing.gpg | gpg --dearmor -o /usr/share/keyrings/angie-archive-keyring.gpg

    # Add Angie repository
    log_info "Adding Angie repository..."
    echo "deb [signed-by=/usr/share/keyrings/angie-archive-keyring.gpg] https://download.angie.software/angie/${OS_ID}/ ${OS_VERSION} main" > /etc/apt/sources.list.d/angie.list

    # Update and install
    apt-get update
    apt-get install -y angie angie-module-brotli

    log_info "Angie installed successfully"
    angie -v
}

install_certbot() {
    log_step "Installing Certbot"

    # Install Certbot
    apt-get install -y certbot

    log_info "Certbot installed successfully"
    certbot --version
}

setup_directories() {
    log_step "Setting up directories"

    # Create required directories
    mkdir -p /var/www/certbot
    mkdir -p /var/log/angie
    mkdir -p /etc/angie/conf.d
    mkdir -p /etc/angie/snippets

    # Set permissions
    chown -R www-data:www-data /var/www/certbot
    chown -R www-data:adm /var/log/angie

    log_info "Directories created"
}

copy_configs() {
    log_step "Copying configuration files"

    # Backup existing config if present
    if [ -f /etc/angie/angie.conf ]; then
        cp /etc/angie/angie.conf /etc/angie/angie.conf.backup.$(date +%Y%m%d_%H%M%S)
        log_info "Backed up existing angie.conf"
    fi

    # Copy main config
    cp "${SCRIPT_DIR}/angie.conf" /etc/angie/angie.conf
    log_info "Copied angie.conf"

    # Copy conf.d files (except template)
    cp "${SCRIPT_DIR}/conf.d/ssl.conf" /etc/angie/conf.d/
    cp "${SCRIPT_DIR}/conf.d/security-headers.conf" /etc/angie/conf.d/
    cp "${SCRIPT_DIR}/conf.d/rate-limit.conf" /etc/angie/conf.d/
    log_info "Copied conf.d files"

    # Copy snippets
    cp "${SCRIPT_DIR}/snippets/"*.conf /etc/angie/snippets/
    log_info "Copied snippet files"

    # Load brotli module
    if [ ! -f /etc/angie/modules-enabled/50-mod-brotli.conf ]; then
        mkdir -p /etc/angie/modules-enabled
        echo "load_module modules/ngx_http_brotli_filter_module.so;" > /etc/angie/modules-enabled/50-mod-brotli.conf
        echo "load_module modules/ngx_http_brotli_static_module.so;" >> /etc/angie/modules-enabled/50-mod-brotli.conf
        log_info "Enabled brotli module"
    fi

    log_info "Configuration files copied"
}

generate_site_config() {
    log_step "Generating site configuration"

    # Load environment variables
    if [ -f "${PROJECT_DIR}/.env" ]; then
        set -a
        source "${PROJECT_DIR}/.env"
        set +a
        log_info "Loaded environment from .env"
    else
        log_warn ".env file not found. Please set DOMAIN before running setup-ssl.sh"
        return
    fi

    if [ -z "$DOMAIN" ]; then
        log_warn "DOMAIN not set. Please set it in .env before running setup-ssl.sh"
        return
    fi

    # Generate config from template
    envsubst '${DOMAIN}' < "${SCRIPT_DIR}/conf.d/faithtracker.conf.template" > /etc/angie/conf.d/faithtracker.conf
    log_info "Generated faithtracker.conf for domain: $DOMAIN"
}

setup_certbot_renewal() {
    log_step "Setting up automatic certificate renewal"

    # Create renewal hook to reload Angie
    mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    cat > /etc/letsencrypt/renewal-hooks/deploy/reload-angie.sh << 'EOF'
#!/bin/bash
# Reload Angie after certificate renewal
systemctl reload angie
EOF
    chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-angie.sh

    # Enable certbot timer (systemd-based renewal)
    if systemctl list-unit-files | grep -q certbot.timer; then
        systemctl enable certbot.timer
        systemctl start certbot.timer
        log_info "Certbot systemd timer enabled"
    else
        # Fallback to cron
        echo "0 0,12 * * * root certbot renew --quiet --deploy-hook 'systemctl reload angie'" > /etc/cron.d/certbot-renewal
        log_info "Certbot cron job created"
    fi

    log_info "Automatic renewal configured"
}

test_config() {
    log_step "Testing Angie configuration"

    if angie -t; then
        log_info "Configuration test passed"
    else
        log_error "Configuration test failed!"
        exit 1
    fi
}

start_angie() {
    log_step "Starting Angie"

    systemctl enable angie
    systemctl restart angie

    if systemctl is-active --quiet angie; then
        log_info "Angie is running"
    else
        log_error "Angie failed to start"
        systemctl status angie
        exit 1
    fi
}

print_next_steps() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     Angie Installation Complete!                           ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Make sure your .env file has DOMAIN and ACME_EMAIL set:"
    echo "     ${YELLOW}DOMAIN=yourdomain.com${NC}"
    echo "     ${YELLOW}ACME_EMAIL=admin@yourdomain.com${NC}"
    echo ""
    echo "  2. Point your DNS records to this server:"
    echo "     ${YELLOW}yourdomain.com     -> [server IP]${NC}"
    echo "     ${YELLOW}api.yourdomain.com -> [server IP]${NC}"
    echo ""
    echo "  3. Run the SSL setup script:"
    echo "     ${GREEN}sudo ./angie/setup-ssl.sh${NC}"
    echo ""
    echo "  4. Start Docker services:"
    echo "     ${GREEN}docker compose up -d${NC}"
    echo ""
    echo "  5. Verify everything is working:"
    echo "     ${GREEN}./scripts/validate-deployment.sh${NC}"
    echo ""
}

# ===================
# Main
# ===================

main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     FaithTracker - Angie Installation                      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_root
    check_os
    install_dependencies
    install_angie
    install_certbot
    setup_directories
    copy_configs
    generate_site_config
    setup_certbot_renewal
    test_config
    start_angie
    print_next_steps
}

main "$@"
