#!/bin/bash

#################################################################################
# FaithTracker - World-Class Automated Installation Script
# For Debian 12/Ubuntu 20.04+
#################################################################################
#
# Features:
#   - Pre-flight system checks (disk, RAM, network)
#   - Parallel installations for speed
#   - Beautiful progress indicators with ETA
#   - Automatic firewall configuration
#   - Swap setup for low-memory systems
#   - Comprehensive error handling with recovery hints
#   - Version tracking and health verification
#
# Usage:
#   sudo bash install.sh
#
#################################################################################

# Exit on error but allow us to handle it gracefully
set -euo pipefail

#################################################################################
# CONSTANTS & CONFIGURATION
#################################################################################

readonly VERSION="2.1.0"
readonly MIN_DISK_GB=5
readonly MIN_RAM_MB=1024
readonly RECOMMENDED_RAM_MB=2048
readonly INSTALL_DIR="/opt/faithtracker"
readonly LOG_FILE="/var/log/faithtracker_install.log"
readonly BACKUP_DIR="/var/backups/faithtracker"
readonly TOTAL_STEPS=16
readonly NODE_VERSION="18"

# Track timing
START_TIME=$(date +%s)
CURRENT_STEP=0

#################################################################################
# COLORS & STYLING
#################################################################################

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly WHITE='\033[1;37m'
readonly GRAY='\033[0;90m'
readonly NC='\033[0m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'

# Unicode symbols
readonly CHECKMARK="${GREEN}✓${NC}"
readonly CROSSMARK="${RED}✗${NC}"
readonly ARROW="${CYAN}➜${NC}"
readonly BULLET="${BLUE}●${NC}"
readonly STAR="${YELLOW}★${NC}"

#################################################################################
# LOGGING SETUP
#################################################################################

setup_logging() {
    # Create log file with proper permissions
    touch "$LOG_FILE" 2>/dev/null || LOG_FILE="/tmp/faithtracker_install.log"
    exec 3>&1 4>&2
    echo "═══════════════════════════════════════════════════════════════════" >> "$LOG_FILE"
    echo "FaithTracker Installation Log - $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    echo "═══════════════════════════════════════════════════════════════════" >> "$LOG_FILE"
}

log() {
    echo "[$(date '+%H:%M:%S')] $1" >> "$LOG_FILE"
}

#################################################################################
# DISPLAY FUNCTIONS
#################################################################################

show_banner() {
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
    ║              Multi-Campus Pastoral Care Management System             ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    echo -e "                    ${DIM}Installer v${VERSION}${NC}"
    echo ""
}

show_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    local percent=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    local filled=$((percent / 5))
    local empty=$((20 - filled))

    # Calculate ETA
    local elapsed=$(($(date +%s) - START_TIME))
    local eta="calculating..."
    if [ $CURRENT_STEP -gt 1 ]; then
        local remaining_steps=$((TOTAL_STEPS - CURRENT_STEP))
        local avg_time=$((elapsed / (CURRENT_STEP - 1)))
        local eta_seconds=$((remaining_steps * avg_time))
        if [ $eta_seconds -gt 60 ]; then
            eta="~$((eta_seconds / 60))m remaining"
        else
            eta="~${eta_seconds}s remaining"
        fi
    fi

    echo ""
    echo -e "${WHITE}${BOLD}[$CURRENT_STEP/$TOTAL_STEPS]${NC} $1"
    printf "${CYAN}["
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
    printf "] ${percent}%% ${DIM}(${eta})${NC}\n"
}

print_info() {
    echo -e "  ${BULLET} $1" | tee -a "$LOG_FILE"
}

print_success() {
    echo -e "  ${CHECKMARK} ${GREEN}$1${NC}" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "  ${YELLOW}⚠${NC}  $1" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "  ${CROSSMARK} ${RED}$1${NC}" | tee -a "$LOG_FILE"
}

show_build_error() {
    local context="${1:-Build}"
    echo ""
    echo -e "  ${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${RED}${BOLD}$context Error Details:${NC}"
    echo -e "  ${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    # Show last 40 lines of log file with proper formatting
    if [ -f "$LOG_FILE" ]; then
        tail -40 "$LOG_FILE" | while IFS= read -r line; do
            echo -e "  ${DIM}│${NC} $line"
        done
    fi
    echo ""
    echo -e "  ${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${YELLOW}Full log: ${LOG_FILE}${NC}"
    echo ""
}

print_step() {
    echo -e "  ${ARROW} $1"
}

show_spinner() {
    local pid=$1
    local message=$2
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0

    printf "  ${CYAN}"
    while kill -0 $pid 2>/dev/null; do
        printf "\r  ${spin:$i:1} ${message}..."
        i=$(( (i+1) % 10 ))
        sleep 0.1
    done
    printf "\r"
}

#################################################################################
# ERROR HANDLING
#################################################################################

cleanup_on_error() {
    echo ""
    print_error "Installation failed at step $CURRENT_STEP"
    echo ""
    echo -e "${YELLOW}${BOLD}Troubleshooting:${NC}"
    echo -e "  1. Check the log file: ${CYAN}cat $LOG_FILE${NC}"
    echo -e "  2. Verify your internet connection"
    echo -e "  3. Ensure you have enough disk space (${MIN_DISK_GB}GB required)"
    echo -e "  4. Check if ports 80, 443, and 8001 are available"
    echo ""
    echo -e "${CYAN}You can safely re-run this script after fixing the issue.${NC}"
    exit 1
}

trap cleanup_on_error ERR

#################################################################################
# PRE-FLIGHT CHECKS
#################################################################################

check_root() {
    show_progress "Checking permissions"
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root or with sudo"
        echo -e "  ${ARROW} Run: ${CYAN}sudo bash $0${NC}"
        exit 1
    fi
    print_success "Running with root privileges"
}

detect_os() {
    show_progress "Detecting operating system"

    if [ ! -f /etc/os-release ]; then
        print_error "Cannot detect OS. Supported: Debian 12, Ubuntu 20.04+"
        exit 1
    fi

    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID

    print_info "Detected: $PRETTY_NAME"

    case "$OS" in
        debian)
            if [ "${VER%%.*}" -lt 11 ]; then
                print_error "Debian 11+ required. Found: Debian $VER"
                exit 1
            fi
            ;;
        ubuntu)
            if [ "${VER%%.*}" -lt 20 ]; then
                print_error "Ubuntu 20.04+ required. Found: Ubuntu $VER"
                exit 1
            fi
            ;;
        *)
            print_error "Unsupported OS: $OS. Use Debian or Ubuntu."
            exit 1
            ;;
    esac

    print_success "OS compatibility verified"
}

check_system_resources() {
    show_progress "Checking system resources"

    # Check disk space
    local available_gb=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
    if [ "$available_gb" -lt "$MIN_DISK_GB" ]; then
        print_error "Insufficient disk space: ${available_gb}GB available, ${MIN_DISK_GB}GB required"
        exit 1
    fi
    print_success "Disk space: ${available_gb}GB available"

    # Check RAM
    local total_ram_mb=$(free -m | awk 'NR==2 {print $2}')
    if [ "$total_ram_mb" -lt "$MIN_RAM_MB" ]; then
        print_error "Insufficient RAM: ${total_ram_mb}MB available, ${MIN_RAM_MB}MB required"
        exit 1
    fi

    if [ "$total_ram_mb" -lt "$RECOMMENDED_RAM_MB" ]; then
        print_warning "RAM: ${total_ram_mb}MB (${RECOMMENDED_RAM_MB}MB recommended)"
        print_info "Will configure swap space for optimal performance"
        SETUP_SWAP=true
    else
        print_success "RAM: ${total_ram_mb}MB"
        SETUP_SWAP=false
    fi

    # Check CPU cores
    local cpu_cores=$(nproc)
    print_success "CPU cores: $cpu_cores"
}

check_network() {
    show_progress "Checking network connectivity"

    # Test connectivity
    if ! ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
        print_error "No internet connection detected"
        exit 1
    fi
    print_success "Internet connection verified"

    # Test DNS
    if ! ping -c 1 -W 5 google.com &>/dev/null; then
        print_warning "DNS resolution may be slow"
    fi

    # Check if required ports are available
    for port in 80 443; do
        if ss -tuln | grep -q ":$port "; then
            print_warning "Port $port is already in use"
        fi
    done
}

check_repository() {
    show_progress "Validating repository"

    if [ ! -f "$PWD/backend/server.py" ] || [ ! -f "$PWD/frontend/package.json" ]; then
        print_error "Not running from FaithTracker repository"
        echo -e "  ${ARROW} Clone the repo first: ${CYAN}git clone <repo-url>${NC}"
        echo -e "  ${ARROW} Then run: ${CYAN}cd faithtracker && sudo bash install.sh${NC}"
        exit 1
    fi

    # Get version from package.json if available
    if command -v jq &>/dev/null; then
        APP_VERSION=$(jq -r '.version // "2.0.0"' frontend/package.json 2>/dev/null || echo "2.0.0")
    else
        APP_VERSION="2.0.0"
    fi
    print_success "Repository validated (v${APP_VERSION})"
}

show_preflight_summary() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${CHECKMARK} ${BOLD}Pre-flight checks passed!${NC}                                      ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}Installation will:${NC}"
    echo -e "  ${BULLET} Install Python 3.11, Node.js ${NODE_VERSION}, MongoDB 7.0, Nginx"
    echo -e "  ${BULLET} Install Granian (Rust ASGI server) + msgspec (fast JSON)"
    echo -e "  ${BULLET} Configure firewall (UFW) and SSL certificates"
    echo -e "  ${BULLET} Create 'faithtracker' system user"
    echo -e "  ${BULLET} Set up automatic service management"
    echo ""
    echo -e "${YELLOW}Estimated time: 10-15 minutes${NC}"
    echo ""
    read -p "Press Enter to begin installation or Ctrl+C to cancel..."
}

#################################################################################
# INSTALLATION FUNCTIONS
#################################################################################

update_system() {
    show_progress "Updating system packages"

    print_step "Updating package lists"
    apt-get update >> "$LOG_FILE" 2>&1

    print_step "Upgrading installed packages"
    DEBIAN_FRONTEND=noninteractive apt-get upgrade -y >> "$LOG_FILE" 2>&1

    print_step "Installing essential tools"
    apt-get install -y curl wget git rsync jq ufw software-properties-common \
        build-essential libffi-dev >> "$LOG_FILE" 2>&1

    print_success "System packages updated"
}

setup_swap() {
    if [ "$SETUP_SWAP" = true ]; then
        show_progress "Configuring swap space"

        if [ -f /swapfile ]; then
            print_info "Swap file already exists"
        else
            print_step "Creating 2GB swap file"
            fallocate -l 2G /swapfile >> "$LOG_FILE" 2>&1
            chmod 600 /swapfile
            mkswap /swapfile >> "$LOG_FILE" 2>&1
            swapon /swapfile >> "$LOG_FILE" 2>&1
            echo '/swapfile none swap sw 0 0' >> /etc/fstab
            print_success "Swap space configured (2GB)"
        fi
    else
        show_progress "Swap configuration (skipped - sufficient RAM)"
        print_info "System has adequate RAM, skipping swap setup"
    fi
}

install_python() {
    show_progress "Installing Python"

    if command -v python3 &>/dev/null; then
        local py_version=$(python3 --version | awk '{print $2}')
        local py_major=$(echo $py_version | cut -d. -f1)
        local py_minor=$(echo $py_version | cut -d. -f2)

        if [ "$py_major" -ge 3 ] && [ "$py_minor" -ge 9 ]; then
            print_success "Python $py_version already installed"
            apt-get install -y python3-pip python3-venv python3-dev >> "$LOG_FILE" 2>&1
            return
        fi
    fi

    print_step "Installing Python 3.11"
    apt-get install -y python3 python3-pip python3-venv python3-dev >> "$LOG_FILE" 2>&1
    print_success "Python $(python3 --version | awk '{print $2}') installed"
}

install_nodejs() {
    show_progress "Installing Node.js and Yarn"

    if command -v node &>/dev/null; then
        local node_ver=$(node --version | tr -d 'v' | cut -d. -f1)
        if [ "$node_ver" -ge 18 ]; then
            print_success "Node.js $(node --version) already installed"
        else
            print_step "Upgrading Node.js to v${NODE_VERSION}"
            curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - >> "$LOG_FILE" 2>&1
            apt-get install -y nodejs >> "$LOG_FILE" 2>&1
        fi
    else
        print_step "Installing Node.js ${NODE_VERSION}.x LTS"
        curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - >> "$LOG_FILE" 2>&1
        apt-get install -y nodejs >> "$LOG_FILE" 2>&1
    fi

    if ! command -v yarn &>/dev/null; then
        print_step "Installing Yarn"
        npm install -g yarn >> "$LOG_FILE" 2>&1
    fi

    print_success "Node.js $(node --version) and Yarn $(yarn --version) ready"
}

install_mongodb() {
    show_progress "Setting up MongoDB"

    if command -v mongod &>/dev/null; then
        print_info "MongoDB already installed"
        systemctl start mongod 2>/dev/null || true
        systemctl enable mongod 2>/dev/null || true
        MONGODB_REMOTE=false
        print_success "Local MongoDB ready"
        return
    fi

    echo ""
    echo -e "  ${YELLOW}MongoDB not found on this system${NC}"
    echo -e "  ${BULLET} Option 1: Install MongoDB locally (recommended)"
    echo -e "  ${BULLET} Option 2: Use remote MongoDB (Atlas, etc.)"
    echo ""
    read -p "  Install MongoDB locally? (Y/n): " -n 1 -r MONGODB_CHOICE
    echo ""

    if [[ $MONGODB_CHOICE =~ ^[Nn]$ ]]; then
        MONGODB_REMOTE=true
        print_info "Will use remote MongoDB connection"
        return
    fi

    print_step "Adding MongoDB 7.0 repository"
    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
        gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg >> "$LOG_FILE" 2>&1

    if [[ "$OS" == "debian" ]]; then
        echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] http://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" \
            > /etc/apt/sources.list.d/mongodb-org-7.0.list
    else
        echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] http://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" \
            > /etc/apt/sources.list.d/mongodb-org-7.0.list
    fi

    print_step "Installing MongoDB"
    apt-get update >> "$LOG_FILE" 2>&1
    apt-get install -y mongodb-org >> "$LOG_FILE" 2>&1

    systemctl start mongod
    systemctl enable mongod >> "$LOG_FILE" 2>&1

    MONGODB_REMOTE=false
    print_success "MongoDB 7.0 installed and running"
}

install_nginx() {
    show_progress "Installing Nginx web server"

    if command -v nginx &>/dev/null; then
        print_info "Nginx already installed"
    else
        print_step "Installing Nginx"
        apt-get install -y nginx >> "$LOG_FILE" 2>&1
    fi

    systemctl start nginx 2>/dev/null || true
    systemctl enable nginx >> "$LOG_FILE" 2>&1
    print_success "Nginx ready"
}

create_app_user() {
    show_progress "Creating application user"

    if id "faithtracker" &>/dev/null; then
        print_info "User 'faithtracker' already exists"
    else
        useradd -m -s /bin/bash faithtracker >> "$LOG_FILE" 2>&1
        print_success "User 'faithtracker' created"
    fi
}

setup_app_directory() {
    show_progress "Setting up application directory"

    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Directory $INSTALL_DIR already exists"
        echo ""
        read -p "  Backup existing and reinstall? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mkdir -p "$BACKUP_DIR"
            local backup_name="faithtracker_$(date +%Y%m%d_%H%M%S)"
            print_step "Creating backup at $BACKUP_DIR/$backup_name"
            mv "$INSTALL_DIR" "$BACKUP_DIR/$backup_name"
            print_success "Backup created"
        else
            print_error "Installation cancelled"
            exit 1
        fi
    fi

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/backend/uploads"

    print_step "Copying application files"
    rsync -a --exclude='.git' --exclude='node_modules' --exclude='venv' \
        --exclude='__pycache__' --exclude='*.pyc' --exclude='build' \
        . "$INSTALL_DIR/" >> "$LOG_FILE" 2>&1

    chown -R faithtracker:faithtracker "$INSTALL_DIR"
    print_success "Application files installed"
}

configure_environment() {
    show_progress "Configuring application"

    # Generate secrets
    local JWT_SECRET=$(openssl rand -hex 32)
    local ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || openssl rand -base64 32)

    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${BOLD}Configuration Wizard${NC}                                           ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # MongoDB URL
    if [ "$MONGODB_REMOTE" = true ]; then
        echo -e "  ${BULLET} ${BOLD}MongoDB Connection${NC}"
        echo -e "    Example: mongodb+srv://user:pass@cluster.mongodb.net/dbname"
        while true; do
            read -p "    MongoDB URL: " MONGO_URL
            if [ -n "$MONGO_URL" ]; then break; fi
            print_error "MongoDB URL is required"
        done
    else
        MONGO_URL="mongodb://localhost:27017"
        print_info "Using local MongoDB: $MONGO_URL"
    fi

    # Database name
    echo ""
    read -p "  Database name [pastoral_care_db]: " DB_NAME
    DB_NAME=${DB_NAME:-pastoral_care_db}

    # Domain name
    echo ""
    echo -e "  ${BULLET} ${BOLD}Domain Configuration${NC}"
    echo -e "    FaithTracker uses subdomain architecture:"
    echo -e "    - Frontend: https://DOMAIN"
    echo -e "    - API:      https://api.DOMAIN"
    echo ""
    while true; do
        read -p "    Main domain (e.g., faithtracker.church.org): " DOMAIN_NAME
        if [ -n "$DOMAIN_NAME" ]; then break; fi
        print_error "Domain name is required"
    done
    API_DOMAIN="api.${DOMAIN_NAME}"
    print_info "API will be at: ${API_DOMAIN}"

    # Backend port
    echo ""
    read -p "  Backend API port [8001]: " BACKEND_PORT
    BACKEND_PORT=${BACKEND_PORT:-8001}

    # Validate port
    if ! [[ "$BACKEND_PORT" =~ ^[0-9]+$ ]] || [ "$BACKEND_PORT" -lt 1024 ] || [ "$BACKEND_PORT" -gt 65535 ]; then
        print_warning "Invalid port. Using default 8001"
        BACKEND_PORT=8001
    fi

    # Church name
    echo ""
    read -p "  Church/Organization name [GKBJ]: " CHURCH_NAME
    CHURCH_NAME=${CHURCH_NAME:-GKBJ}

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
        if [ ${#ADMIN_PASSWORD} -ge 8 ]; then
            read -s -p "    Confirm password: " ADMIN_PASSWORD_CONFIRM
            echo ""
            if [ "$ADMIN_PASSWORD" = "$ADMIN_PASSWORD_CONFIRM" ]; then break; fi
            print_error "Passwords do not match"
        else
            print_error "Password must be at least 8 characters"
        fi
    done

    # SSL Setup
    echo ""
    echo -e "  ${BULLET} ${BOLD}SSL/HTTPS Configuration${NC}"
    echo -e "    Requires domain to point to this server's IP"
    read -p "    Enable SSL with Let's Encrypt? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ENABLE_SSL=true
        HTTP_PROTO="https"
    else
        ENABLE_SSL=false
        HTTP_PROTO="http"
    fi

    # Show summary
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}  ${BOLD}Configuration Summary${NC}                                          ${GREEN}║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo -e "  ${BULLET} MongoDB:      ${CYAN}$(echo $MONGO_URL | sed 's/:.*@/:***@/')${NC}"
    echo -e "  ${BULLET} Database:     ${CYAN}$DB_NAME${NC}"
    echo -e "  ${BULLET} Frontend:     ${CYAN}${HTTP_PROTO}://$DOMAIN_NAME${NC}"
    echo -e "  ${BULLET} API:          ${CYAN}${HTTP_PROTO}://$API_DOMAIN${NC}"
    echo -e "  ${BULLET} Backend Port: ${CYAN}$BACKEND_PORT${NC}"
    echo -e "  ${BULLET} SSL/HTTPS:    ${CYAN}$([ "$ENABLE_SSL" = true ] && echo "Enabled" || echo "Disabled")${NC}"
    echo -e "  ${BULLET} Church:       ${CYAN}$CHURCH_NAME${NC}"
    echo -e "  ${BULLET} Admin:        ${CYAN}$ADMIN_EMAIL${NC}"
    echo ""
    read -p "  Proceed with installation? (Y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_error "Installation cancelled"
        exit 1
    fi

    # Create backend .env
    cat > "$INSTALL_DIR/backend/.env" << EOF
# FaithTracker Backend Configuration
# Generated: $(date '+%Y-%m-%d %H:%M:%S')

MONGO_URL="$MONGO_URL"
DB_NAME="$DB_NAME"
ALLOWED_ORIGINS="${HTTP_PROTO}://$DOMAIN_NAME,${HTTP_PROTO}://www.$DOMAIN_NAME"
FRONTEND_URL="${HTTP_PROTO}://$DOMAIN_NAME"
JWT_SECRET_KEY="$JWT_SECRET"
ENCRYPTION_KEY="$ENCRYPTION_KEY"
CHURCH_NAME="$CHURCH_NAME"
BACKEND_PORT="$BACKEND_PORT"
EOF

    # Create frontend .env
    cat > "$INSTALL_DIR/frontend/.env" << EOF
# FaithTracker Frontend Configuration
# Generated: $(date '+%Y-%m-%d %H:%M:%S')

REACT_APP_BACKEND_URL="${HTTP_PROTO}://$API_DOMAIN"
WDS_SOCKET_PORT=$([ "$ENABLE_SSL" = true ] && echo "443" || echo "80")
REACT_APP_ENABLE_VISUAL_EDITS=false
EOF

    # Create version file
    echo "$APP_VERSION" > "$INSTALL_DIR/.version"
    echo "$(date +%s)" > "$INSTALL_DIR/.installed_at"

    chown faithtracker:faithtracker "$INSTALL_DIR/backend/.env"
    chown faithtracker:faithtracker "$INSTALL_DIR/frontend/.env"

    print_success "Configuration saved"
}

setup_backend() {
    show_progress "Setting up backend (Python)"

    cd "$INSTALL_DIR/backend"

    print_step "Creating Python virtual environment"
    sudo -u faithtracker python3 -m venv venv >> "$LOG_FILE" 2>&1

    print_step "Installing Python dependencies"
    sudo -u faithtracker "$INSTALL_DIR/backend/venv/bin/pip" install --upgrade pip >> "$LOG_FILE" 2>&1
    sudo -u faithtracker "$INSTALL_DIR/backend/venv/bin/pip" install -r requirements.txt >> "$LOG_FILE" 2>&1 &
    local pip_pid=$!
    show_spinner $pip_pid "Installing Python packages"
    if ! wait $pip_pid; then
        print_error "Python dependencies installation failed"
        show_build_error "Python pip install"
        exit 1
    fi

    print_step "Initializing database"
    sudo -u faithtracker "$INSTALL_DIR/backend/venv/bin/python" init_db.py \
        --admin-email "$ADMIN_EMAIL" \
        --admin-password "$ADMIN_PASSWORD" \
        --church-name "$CHURCH_NAME" >> "$LOG_FILE" 2>&1 || {
        print_error "Database initialization failed"
        exit 1
    }

    print_step "Creating database indexes"
    sudo -u faithtracker "$INSTALL_DIR/backend/venv/bin/python" create_indexes.py >> "$LOG_FILE" 2>&1 || true

    print_success "Backend setup complete"
}

setup_frontend() {
    show_progress "Setting up frontend (React)"

    cd "$INSTALL_DIR/frontend"

    print_step "Installing Node.js dependencies"
    sudo -u faithtracker yarn install >> "$LOG_FILE" 2>&1 &
    local yarn_pid=$!
    show_spinner $yarn_pid "Installing packages"
    if ! wait $yarn_pid; then
        print_error "Node.js dependencies installation failed"
        show_build_error "yarn install"
        exit 1
    fi

    print_step "Building production bundle"
    # Increase Node.js memory for build
    export NODE_OPTIONS="--max-old-space-size=2048"
    sudo -u faithtracker yarn build >> "$LOG_FILE" 2>&1 &
    local build_pid=$!

    # Show build progress
    local dots=0
    printf "  "
    while kill -0 $build_pid 2>/dev/null; do
        printf "."
        dots=$((dots + 1))
        if [ $dots -ge 50 ]; then
            printf "\n  "
            dots=0
        fi
        sleep 2
    done
    echo ""

    wait $build_pid || {
        print_error "Frontend build failed"
        show_build_error "yarn build"
        exit 1
    }

    print_success "Frontend build complete"
}

create_systemd_service() {
    show_progress "Creating system service"

    # Create log directory
    mkdir -p /var/log/faithtracker
    chown faithtracker:faithtracker /var/log/faithtracker
    touch /var/log/faithtracker/backend.out.log /var/log/faithtracker/backend.err.log
    chown faithtracker:faithtracker /var/log/faithtracker/backend.out.log /var/log/faithtracker/backend.err.log

    cat > /etc/systemd/system/faithtracker-backend.service << EOF
[Unit]
Description=FaithTracker FastAPI Backend (Granian)
After=network.target mongod.service
Wants=mongod.service

[Service]
Type=simple
User=faithtracker
Group=faithtracker
WorkingDirectory=/opt/faithtracker/backend
Environment="PATH=/opt/faithtracker/backend/venv/bin"
# Granian: Rust-based ASGI server (faster than Uvicorn)
# --http auto: Auto-negotiate HTTP/1.1 or HTTP/2
ExecStart=/opt/faithtracker/backend/venv/bin/granian --interface asgi --host 0.0.0.0 --port $BACKEND_PORT --workers 2 --http auto server:app
Restart=always
RestartSec=10
StandardOutput=append:/var/log/faithtracker/backend.out.log
StandardError=append:/var/log/faithtracker/backend.err.log

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/faithtracker/backend/uploads /var/log/faithtracker
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

    # Create logrotate config for backend logs
    cat > /etc/logrotate.d/faithtracker << 'LOGROTATE'
/var/log/faithtracker/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 faithtracker faithtracker
    sharedscripts
    postrotate
        systemctl reload faithtracker-backend > /dev/null 2>&1 || true
    endscript
}
LOGROTATE

    systemctl daemon-reload
    systemctl enable faithtracker-backend >> "$LOG_FILE" 2>&1
    systemctl start faithtracker-backend

    sleep 3

    if systemctl is-active --quiet faithtracker-backend; then
        print_success "Backend service started"
    else
        print_error "Backend service failed to start"
        echo "  ${ARROW} Check logs: ${CYAN}tail -f /var/log/faithtracker/backend.err.log${NC}"
        exit 1
    fi
}

configure_nginx() {
    show_progress "Configuring web server (dual-domain)"

    # Frontend configuration
    cat > /etc/nginx/sites-available/faithtracker-frontend << EOF
# FaithTracker Frontend Nginx Configuration
# Domain: $DOMAIN_NAME
# Generated: $(date '+%Y-%m-%d %H:%M:%S')

server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;

    root /opt/faithtracker/frontend/build;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    # React SPA routing
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Static assets caching
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
EOF

    # API Backend configuration
    cat > /etc/nginx/sites-available/faithtracker-api << EOF
# FaithTracker API Backend Nginx Configuration
# Domain: $API_DOMAIN
# Generated: $(date '+%Y-%m-%d %H:%M:%S')

server {
    listen 80;
    listen [::]:80;
    server_name $API_DOMAIN;

    # Proxy settings
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";

    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    # File upload limit
    client_max_body_size 20M;

    # Proxy all requests to FastAPI backend
    location / {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:$BACKEND_PORT/health;
        access_log off;
    }

    # Uploads directory
    location /uploads/ {
        alias /opt/faithtracker/backend/uploads/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
EOF

    ln -sf /etc/nginx/sites-available/faithtracker-frontend /etc/nginx/sites-enabled/
    ln -sf /etc/nginx/sites-available/faithtracker-api /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default

    nginx -t >> "$LOG_FILE" 2>&1 || {
        print_error "Nginx configuration test failed"
        exit 1
    }

    systemctl restart nginx
    print_success "Nginx configured for dual-domain"
}

setup_firewall() {
    show_progress "Configuring firewall"

    if ! command -v ufw &>/dev/null; then
        apt-get install -y ufw >> "$LOG_FILE" 2>&1
    fi

    print_step "Setting up UFW rules"
    ufw --force reset >> "$LOG_FILE" 2>&1
    ufw default deny incoming >> "$LOG_FILE" 2>&1
    ufw default allow outgoing >> "$LOG_FILE" 2>&1
    ufw allow ssh >> "$LOG_FILE" 2>&1
    ufw allow 'Nginx Full' >> "$LOG_FILE" 2>&1
    ufw --force enable >> "$LOG_FILE" 2>&1

    print_success "Firewall configured (SSH, HTTP, HTTPS allowed)"
}

setup_ssl() {
    show_progress "Setting up SSL certificates (dual-domain)"

    if [ "$ENABLE_SSL" != true ]; then
        print_info "SSL not enabled during configuration"
        print_info "Enable later:"
        print_info "  Frontend: ${CYAN}sudo certbot --nginx -d $DOMAIN_NAME -d www.$DOMAIN_NAME${NC}"
        print_info "  API:      ${CYAN}sudo certbot --nginx -d $API_DOMAIN${NC}"
        return
    fi

    if ! command -v certbot &>/dev/null; then
        print_step "Installing Certbot"
        apt-get install -y certbot python3-certbot-nginx >> "$LOG_FILE" 2>&1
    fi

    # Certificate for frontend (main domain)
    print_step "Obtaining SSL certificate for frontend ($DOMAIN_NAME)"
    certbot --nginx -d "$DOMAIN_NAME" -d "www.$DOMAIN_NAME" \
        --non-interactive --agree-tos --email "$ADMIN_EMAIL" \
        --redirect >> "$LOG_FILE" 2>&1 && \
    print_success "Frontend SSL certificate installed" || {
        print_warning "Frontend SSL setup failed - verify DNS for $DOMAIN_NAME"
    }

    # Certificate for API (api subdomain)
    print_step "Obtaining SSL certificate for API ($API_DOMAIN)"
    certbot --nginx -d "$API_DOMAIN" \
        --non-interactive --agree-tos --email "$ADMIN_EMAIL" \
        --redirect >> "$LOG_FILE" 2>&1 && \
    print_success "API SSL certificate installed" || {
        print_warning "API SSL setup failed - verify DNS for $API_DOMAIN"
        print_info "Make sure api.$DOMAIN_NAME points to this server's IP"
    }
}

run_health_checks() {
    show_progress "Running health checks"

    sleep 2

    # Test backend API
    print_step "Testing backend API"
    if curl -sf "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
        print_success "Backend API healthy"
    else
        print_warning "Backend health check failed (may still be starting)"
    fi

    # Test frontend build
    print_step "Verifying frontend build"
    if [ -f "$INSTALL_DIR/frontend/build/index.html" ]; then
        print_success "Frontend build verified"
    else
        print_warning "Frontend build not found"
    fi

    # Test web server
    print_step "Testing web server"
    if curl -sf http://localhost/ > /dev/null 2>&1; then
        print_success "Web server responding"
    else
        print_warning "Web server check failed"
    fi
}

print_summary() {
    local elapsed=$(($(date +%s) - START_TIME))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))

    echo ""
    echo -e "${GREEN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║      ✓ ✓ ✓   INSTALLATION COMPLETE!   ✓ ✓ ✓                          ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    echo -e "${BOLD}Installation completed in ${minutes}m ${seconds}s${NC}"
    echo ""
    echo -e "${CYAN}${BOLD}🌐 Access Your Application:${NC}"
    echo -e "   Frontend: ${HTTP_PROTO}://$DOMAIN_NAME"
    echo -e "   API:      ${HTTP_PROTO}://$API_DOMAIN"
    echo ""
    echo -e "${CYAN}${BOLD}👤 Admin Login:${NC}"
    echo -e "   Email:    $ADMIN_EMAIL"
    echo -e "   Password: [as configured]"
    echo ""
    echo -e "${CYAN}${BOLD}📁 Important Locations:${NC}"
    echo -e "   Application:  /opt/faithtracker"
    echo -e "   Install Log:  $LOG_FILE"
    echo -e "   Backend Logs: /var/log/faithtracker/"
    echo ""
    echo -e "${CYAN}${BOLD}📋 View Logs:${NC}"
    echo -e "   ${DIM}tail -f /var/log/faithtracker/backend.out.log${NC}  # stdout"
    echo -e "   ${DIM}tail -f /var/log/faithtracker/backend.err.log${NC}  # stderr"
    echo ""
    echo -e "${CYAN}${BOLD}🔧 Service Management:${NC}"
    echo -e "   sudo systemctl status faithtracker-backend"
    echo -e "   sudo systemctl restart faithtracker-backend"
    echo -e "   sudo systemctl status nginx"
    echo ""
    echo -e "${CYAN}${BOLD}🔄 Updates:${NC}"
    echo -e "   cd /path/to/git/repo && sudo bash update.sh"
    echo ""
    echo -e "${GREEN}${BOLD}Thank you for installing FaithTracker! 🙏${NC}"
    echo ""
}

#################################################################################
# MAIN EXECUTION
#################################################################################

main() {
    setup_logging
    show_banner

    echo -e "${BOLD}Welcome to the FaithTracker Installer${NC}"
    echo ""
    echo "This script will install and configure FaithTracker on your server."
    echo -e "For Debian 12 / Ubuntu 20.04+ | Requires ${YELLOW}~10-15 minutes${NC}"
    echo ""
    echo -e "${BOLD}Requirements:${NC}"
    echo -e "  ${BULLET} Fresh server with 2GB+ RAM"
    echo -e "  ${BULLET} Internet connection"
    echo -e "  ${BULLET} Domain name pointing to this server (recommended)"
    echo ""
    read -p "Press Enter to start pre-flight checks..."

    # Pre-flight checks
    check_root
    detect_os
    check_system_resources
    check_network
    check_repository
    show_preflight_summary

    # Installation
    update_system
    setup_swap
    install_python
    install_nodejs
    install_mongodb
    install_nginx
    create_app_user
    setup_app_directory
    configure_environment
    setup_backend
    setup_frontend
    create_systemd_service
    configure_nginx
    setup_firewall
    setup_ssl
    run_health_checks

    # Done!
    print_summary
}

main "$@"
