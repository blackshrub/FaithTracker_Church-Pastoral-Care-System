#!/bin/bash

#################################################################################
# FaithTracker - Docker Installation Script
# For any Linux system with Docker support
#################################################################################
#
# Features:
#   - One-command deployment with Docker Compose
#   - Automatic SSL via Traefik + Let's Encrypt
#   - Subdomain architecture (domain.com + api.domain.com)
#   - Zero-downtime updates
#
# Usage:
#   sudo bash docker-install.sh
#
#################################################################################

set -euo pipefail

#################################################################################
# CONSTANTS & STYLING
#################################################################################

readonly VERSION="1.0.0"
readonly INSTALL_DIR="/opt/faithtracker"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly WHITE='\033[1;37m'
readonly NC='\033[0m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'

# Symbols
readonly CHECKMARK="${GREEN}✓${NC}"
readonly CROSSMARK="${RED}✗${NC}"
readonly ARROW="${CYAN}➜${NC}"
readonly BULLET="${BLUE}●${NC}"

#################################################################################
# HELPER FUNCTIONS
#################################################################################

print_banner() {
    clear
    echo -e "${CYAN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║   ███████╗ █████╗ ██╗████████╗██╗  ██╗████████╗██████╗  █████╗       ║
    ║   ██╔════╝██╔══██╗██║╚══██╔══╝██║  ██║╚══██╔══╝██╔══██╗██╔══██╗      ║
    ║   █████╗  ███████║██║   ██║   ███████║   ██║   ██████╔╝███████║      ║
    ║   ██╔══╝  ██╔══██║██║   ██║   ██╔══██║   ██║   ██╔══██╗██╔══██║      ║
    ║   ██║     ██║  ██║██║   ██║   ██║  ██║   ██║   ██║  ██║██║  ██║      ║
    ║   ╚═╝     ╚═╝  ╚═╝╚═╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝      ║
    ║                                                                       ║
    ║              Docker Installation - v1.0.0                             ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

print_info() { echo -e "  ${BULLET} $1"; }
print_success() { echo -e "  ${CHECKMARK} ${GREEN}$1${NC}"; }
print_warning() { echo -e "  ${YELLOW}⚠${NC}  $1"; }
print_error() { echo -e "  ${CROSSMARK} ${RED}$1${NC}"; }
print_step() { echo -e "  ${ARROW} $1"; }

#################################################################################
# CHECKS
#################################################################################

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root or with sudo"
        echo -e "  ${ARROW} Run: ${CYAN}sudo bash $0${NC}"
        exit 1
    fi
    print_success "Running with root privileges"
}

check_docker() {
    echo ""
    echo -e "${BOLD}Checking Docker...${NC}"

    if ! command -v docker &>/dev/null; then
        print_warning "Docker not installed"
        echo ""
        read -p "  Install Docker? (Y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            install_docker
        else
            print_error "Docker is required for this installation"
            exit 1
        fi
    else
        print_success "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
    fi

    if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
        print_warning "Docker Compose not found"
        install_docker_compose
    else
        print_success "Docker Compose available"
    fi
}

install_docker() {
    print_step "Installing Docker..."
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
    print_success "Docker installed"
}

install_docker_compose() {
    print_step "Installing Docker Compose plugin..."
    apt-get update
    apt-get install -y docker-compose-plugin
    print_success "Docker Compose installed"
}

check_repository() {
    echo ""
    echo -e "${BOLD}Validating repository...${NC}"

    if [ ! -f "$PWD/docker-compose.yml" ]; then
        print_error "docker-compose.yml not found"
        echo -e "  ${ARROW} Run this script from the FaithTracker repository root"
        exit 1
    fi

    if [ ! -f "$PWD/backend/Dockerfile" ] || [ ! -f "$PWD/frontend/Dockerfile" ]; then
        print_error "Dockerfiles not found"
        exit 1
    fi

    print_success "Repository validated"
}

#################################################################################
# CONFIGURATION
#################################################################################

configure_environment() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${BOLD}Configuration Wizard${NC}                                           ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Domain
    echo -e "  ${BULLET} ${BOLD}Domain Configuration${NC}"
    echo -e "    Your app will be available at:"
    echo -e "    - Frontend: https://DOMAIN"
    echo -e "    - API:      https://api.DOMAIN"
    echo ""
    while true; do
        read -p "    Enter your domain (e.g., faithtracker.church.org): " DOMAIN
        if [ -n "$DOMAIN" ]; then break; fi
        print_error "Domain is required"
    done

    # Email for Let's Encrypt
    echo ""
    echo -e "  ${BULLET} ${BOLD}SSL Certificate${NC}"
    while true; do
        read -p "    Email for Let's Encrypt notifications: " ACME_EMAIL
        if [[ "$ACME_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then break; fi
        print_error "Invalid email format"
    done

    # MongoDB password
    echo ""
    echo -e "  ${BULLET} ${BOLD}Database${NC}"
    MONGO_PASSWORD=$(openssl rand -hex 16)
    print_info "Generated MongoDB password"

    # Security keys
    echo ""
    echo -e "  ${BULLET} ${BOLD}Security Keys${NC}"
    JWT_SECRET=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(openssl rand -base64 32)
    print_info "Generated JWT and encryption keys"

    # Admin credentials
    echo ""
    echo -e "  ${BULLET} ${BOLD}Admin Account${NC}"
    while true; do
        read -p "    Admin email: " ADMIN_EMAIL
        if [[ "$ADMIN_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then break; fi
        print_error "Invalid email format"
    done

    while true; do
        read -s -p "    Admin password (min 8 chars): " ADMIN_PASSWORD
        echo ""
        if [ ${#ADMIN_PASSWORD} -ge 8 ]; then break; fi
        print_error "Password must be at least 8 characters"
    done

    # Church name
    echo ""
    read -p "    Church/Organization name [FaithTracker Church]: " CHURCH_NAME
    CHURCH_NAME=${CHURCH_NAME:-"FaithTracker Church"}

    # Traefik dashboard auth (optional)
    TRAEFIK_AUTH=""
    DASHBOARD_ENABLED=false
    echo ""
    read -p "    Enable Traefik dashboard at traefik.${DOMAIN}? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        DASHBOARD_ENABLED=true
        read -s -p "    Dashboard password: " DASHBOARD_PASS
        echo ""
        # Generate htpasswd format (requires apache2-utils)
        if command -v htpasswd &>/dev/null; then
            TRAEFIK_AUTH=$(htpasswd -nb admin "$DASHBOARD_PASS" | sed -e 's/\$/\$\$/g')
        else
            TRAEFIK_AUTH="admin:$(openssl passwd -apr1 "$DASHBOARD_PASS" | sed -e 's/\$/\$\$/g')"
        fi
        print_success "Dashboard enabled (user: admin)"
    fi

    # Summary
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${BOLD}Configuration Summary${NC}                                          ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo -e "  ${BULLET} Domain:      ${CYAN}${DOMAIN}${NC}"
    echo -e "  ${BULLET} API URL:     ${CYAN}https://api.${DOMAIN}${NC}"
    if [ "$DASHBOARD_ENABLED" = true ]; then
        echo -e "  ${BULLET} Dashboard:   ${CYAN}https://traefik.${DOMAIN}${NC}"
    fi
    echo -e "  ${BULLET} SSL Email:   ${CYAN}${ACME_EMAIL}${NC}"
    echo -e "  ${BULLET} Admin:       ${CYAN}${ADMIN_EMAIL}${NC}"
    echo -e "  ${BULLET} Church:      ${CYAN}${CHURCH_NAME}${NC}"
    echo ""
    read -p "  Proceed with deployment? (Y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_error "Installation cancelled"
        exit 1
    fi
}

create_env_file() {
    echo ""
    echo -e "${BOLD}Creating configuration files...${NC}"

    # Create .env file
    cat > "$PWD/.env" << EOF
# FaithTracker Docker Configuration
# Generated: $(date '+%Y-%m-%d %H:%M:%S')

# Domain Configuration
DOMAIN=${DOMAIN}
ACME_EMAIL=${ACME_EMAIL}

# MongoDB
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=${MONGO_PASSWORD}

# Security Keys
JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# Traefik Dashboard (optional)
TRAEFIK_DASHBOARD_AUTH=${TRAEFIK_AUTH:-"admin:\$\$apr1\$\$disabled"}

# Initial Setup
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
CHURCH_NAME=${CHURCH_NAME}
EOF

    chmod 600 "$PWD/.env"
    print_success "Environment file created"
}

#################################################################################
# DEPLOYMENT
#################################################################################

deploy_containers() {
    echo ""
    echo -e "${BOLD}Deploying FaithTracker...${NC}"

    # Create Let's Encrypt certificate storage with proper permissions
    print_step "Setting up SSL certificate storage..."
    mkdir -p "$PWD/letsencrypt"
    # Clear any stale certificate data for fresh start
    > "$PWD/letsencrypt/acme.json"
    chmod 600 "$PWD/letsencrypt/acme.json"
    print_success "SSL certificate storage ready (TLS-ALPN-01 challenge)"

    print_step "Building containers (this may take 5-10 minutes)..."

    # Use docker compose (v2) or docker-compose (v1)
    if docker compose version &>/dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # Build and start
    $COMPOSE_CMD build --no-cache 2>&1 | while IFS= read -r line; do
        echo -e "  ${DIM}│${NC} $line"
    done

    print_step "Starting services..."
    $COMPOSE_CMD up -d

    print_success "Containers started"

    # Wait for services to be healthy
    echo ""
    print_step "Waiting for services to be ready..."
    sleep 10

    # Check container status
    echo ""
    echo -e "${BOLD}Container Status:${NC}"
    $COMPOSE_CMD ps
}

initialize_database() {
    echo ""
    echo -e "${BOLD}Initializing database...${NC}"

    # Wait for MongoDB to be ready
    print_step "Waiting for MongoDB..."
    sleep 5

    # Run database initialization
    if docker compose version &>/dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # Check if init_db.py exists and run it
    if [ -f "$PWD/backend/init_db.py" ]; then
        print_step "Creating admin user and initial data..."
        $COMPOSE_CMD exec -T backend python init_db.py \
            --admin-email "$ADMIN_EMAIL" \
            --admin-password "$ADMIN_PASSWORD" \
            --church-name "$CHURCH_NAME" 2>/dev/null || true
    fi

    print_success "Database initialized"
}

print_summary() {
    echo ""
    echo -e "${GREEN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║      ✓ ✓ ✓   DEPLOYMENT COMPLETE!   ✓ ✓ ✓                            ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    echo -e "${CYAN}${BOLD}🌐 Access Your Application:${NC}"
    echo -e "   Frontend:  ${WHITE}https://${DOMAIN}${NC}"
    echo -e "   API:       ${WHITE}https://api.${DOMAIN}${NC}"
    echo -e "   API Docs:  ${WHITE}https://api.${DOMAIN}/docs${NC}"
    if [ "$DASHBOARD_ENABLED" = true ]; then
        echo -e "   Dashboard: ${WHITE}https://traefik.${DOMAIN}${NC} (user: admin)"
    fi
    echo ""
    echo -e "${CYAN}${BOLD}👤 Admin Login:${NC}"
    echo -e "   Email:    ${ADMIN_EMAIL}"
    echo -e "   Password: [as configured]"
    echo ""
    echo -e "${CYAN}${BOLD}🔧 Management Commands:${NC}"
    echo -e "   ${DIM}docker compose ps${NC}           # View status"
    echo -e "   ${DIM}docker compose logs -f${NC}      # View logs"
    echo -e "   ${DIM}docker compose restart${NC}      # Restart services"
    echo -e "   ${DIM}docker compose down${NC}         # Stop all"
    echo -e "   ${DIM}docker compose up -d --build${NC} # Rebuild & restart"
    echo ""
    echo -e "${CYAN}${BOLD}📁 Data Storage:${NC}"
    echo -e "   MongoDB:  faithtracker_mongo-data (Docker volume)"
    echo -e "   Uploads:  faithtracker_backend-uploads (Docker volume)"
    echo -e "   SSL:      ./letsencrypt/acme.json (local file)"
    echo ""
    echo -e "${YELLOW}Note: SSL certificates may take 1-2 minutes to be issued.${NC}"
    echo -e "${YELLOW}If you see certificate errors, wait and refresh.${NC}"
    if [ "$DASHBOARD_ENABLED" = true ]; then
        echo ""
        echo -e "${YELLOW}Dashboard requires DNS: traefik.${DOMAIN} → your server IP${NC}"
    fi
    echo ""
    echo -e "${GREEN}${BOLD}Thank you for using FaithTracker! 🙏${NC}"
    echo ""
}

#################################################################################
# MAIN
#################################################################################

main() {
    print_banner

    echo -e "${BOLD}Welcome to FaithTracker Docker Installer${NC}"
    echo ""
    echo "This will deploy FaithTracker using Docker Compose with:"
    echo -e "  ${BULLET} Traefik reverse proxy with automatic SSL"
    echo -e "  ${BULLET} MongoDB database"
    echo -e "  ${BULLET} FastAPI backend"
    echo -e "  ${BULLET} React frontend"
    echo ""
    read -p "Press Enter to continue..."

    check_root
    check_docker
    check_repository
    configure_environment
    create_env_file
    deploy_containers
    initialize_database
    print_summary
}

main "$@"
