#!/bin/bash

#################################################################################
# FaithTracker - Automated Installation Script for Debian 12/Ubuntu 20.04+
#################################################################################
#
# This script automates the complete installation and configuration of
# FaithTracker on a fresh Debian/Ubuntu server.
#
# Usage:
#   sudo bash install.sh
#
#################################################################################

# Exit on error but allow us to handle it gracefully
set -eo pipefail  # Removed -u flag to allow unbound variables during prompts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Global variables
LOG_FILE="/var/log/faithtracker_install.log"
INSTALL_DIR="/opt/faithtracker"
TOTAL_STEPS=15
CURRENT_STEP=0

# Create log file
touch "$LOG_FILE" 2>/dev/null || LOG_FILE="/tmp/faithtracker_install.log"
echo "=== FaithTracker Installation started at $(date) ===" > "$LOG_FILE"

#################################################################################
# HELPER FUNCTIONS
#################################################################################

# Progress indicator
show_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "${MAGENTA}[Step $CURRENT_STEP/$TOTAL_STEPS]${NC} $1"
}

# Print functions with timestamps
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

print_success() {
    echo -e "${GREEN}[✓ SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}[⚠ WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "${RED}[✗ ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# Progress bar
show_spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while ps -p $pid > /dev/null 2>&1; do
        local temp=${spinstr#?}
        printf " ${CYAN}[%c]${NC}  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Error handler
trap 'handle_error $? $LINENO $BASH_COMMAND' ERR

handle_error() {
    local exit_code=$1
    local line_number=$2
    local command="$3"
    
    echo ""
    print_error "Installation failed at line $line_number with exit code $exit_code"
    print_error "Failed command: $command"
    print_error "Check the log file for details: $LOG_FILE"
    echo ""
    echo -e "${YELLOW}Common solutions:${NC}"
    echo "  1. Check your internet connection"
    echo "  2. Ensure you have sudo/root privileges"
    echo "  3. Verify MongoDB connection if using remote database"
    echo "  4. Review the log file: cat $LOG_FILE"
    echo ""
    echo -e "${CYAN}You can re-run this script after fixing the issue${NC}"
    exit $exit_code
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Validate email format
validate_email() {
    [[ "$1" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]
}

# Validate domain format
validate_domain() {
    [[ "$1" =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?\.[a-zA-Z]{2,}$ ]]
}

#################################################################################
# INSTALLATION FUNCTIONS
#################################################################################

# Check if running as root
check_root() {
    show_progress "Checking permissions"
    if [[ $EUID -ne 0 ]]; then
       print_error "This script must be run as root or with sudo"
       echo "Please run: sudo bash $0"
       exit 1
    fi
    print_success "Running with proper permissions"
}

# Detect OS
detect_os() {
    show_progress "Detecting operating system"
    
    if [ ! -f /etc/os-release ]; then
        print_error "Cannot detect OS. This script supports Debian 12 and Ubuntu 20.04+"
        exit 1
    fi
    
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
    
    print_info "Detected: $PRETTY_NAME"
    
    if [[ "$OS" != "debian" && "$OS" != "ubuntu" ]]; then
        print_error "Unsupported OS. This script only supports Debian and Ubuntu."
        exit 1
    fi
    
    print_success "OS compatibility confirmed"
}

# Update system
update_system() {
    show_progress "Updating system packages"
    
    print_info "This may take several minutes..."
    {
        apt update
        DEBIAN_FRONTEND=noninteractive apt upgrade -y
        apt install -y build-essential curl wget git rsync
    } >> "$LOG_FILE" 2>&1
    
    print_success "System updated successfully"
}

# Install Python
install_python() {
    show_progress "Installing Python"
    
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_info "Python $PYTHON_VERSION already installed"
    else
        print_info "Installing Python 3..."
        apt install -y python3 python3-pip python3-venv python3-dev >> "$LOG_FILE" 2>&1
    fi
    
    # Ensure python3-venv is installed (even if Python was already there)
    print_info "Ensuring python3-venv is installed..."
    apt install -y python3-venv >> "$LOG_FILE" 2>&1
    
    # Verify Python version is 3.9+
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
        print_error "Python 3.9+ is required. Found: $(python3 --version)"
        exit 1
    fi
    
    print_success "Python $(python3 --version | awk '{print $2}') ready"
}

# Install Node.js & Yarn
install_nodejs() {
    show_progress "Installing Node.js and Yarn"
    
    if command_exists node; then
        NODE_VERSION=$(node --version)
        NODE_MAJOR=$(node --version | cut -d'.' -f1 | sed 's/v//')
        
        if [ "$NODE_MAJOR" -lt 20 ]; then
            print_warning "Node.js $NODE_VERSION is too old. Upgrading to Node.js 20..."
            curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >> "$LOG_FILE" 2>&1
            apt install -y nodejs >> "$LOG_FILE" 2>&1
        else
            print_info "Node.js $NODE_VERSION already installed"
        fi
    else
        print_info "Installing Node.js 20.x LTS..."
        {
            curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
            apt install -y nodejs
        } >> "$LOG_FILE" 2>&1
    fi
    
    if command_exists yarn; then
        print_info "Yarn already installed"
    else
        print_info "Installing Yarn..."
        npm install -g yarn >> "$LOG_FILE" 2>&1
    fi
    
    print_success "Node.js $(node --version) and Yarn ready"
}

# Install MongoDB
install_mongodb() {
    show_progress "Setting up MongoDB"
    
    if command_exists mongod; then
        print_info "MongoDB is already installed"
        systemctl start mongod 2>/dev/null || true
        systemctl enable mongod 2>/dev/null || true
        MONGODB_REMOTE=false
        print_success "Local MongoDB ready"
    else
        echo ""
        print_warning "MongoDB not found on this system"
        echo -e "${CYAN}Options:${NC}"
        echo "  1. Install MongoDB locally (recommended for single-server setup)"
        echo "  2. Use remote/managed MongoDB (e.g., MongoDB Atlas)"
        echo ""
        read -p "Choose option (1 or 2): " -n 1 -r MONGODB_CHOICE
        echo ""
        
        if [[ $MONGODB_CHOICE == "1" ]]; then
            print_info "Installing MongoDB locally..."
            {
                curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
                
                if [[ "$OS" == "debian" ]]; then
                    echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] http://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" > /etc/apt/sources.list.d/mongodb-org-7.0.list
                else
                    echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] http://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-7.0.list
                fi
                
                apt update
                apt install -y mongodb-org
                systemctl start mongod
                systemctl enable mongod
            } >> "$LOG_FILE" 2>&1
            
            MONGODB_REMOTE=false
            print_success "MongoDB installed and started"
        else
            MONGODB_REMOTE=true
            print_info "Will use remote MongoDB connection"
        fi
    fi
}

# Install Nginx
install_nginx() {
    show_progress "Installing web server (Nginx)"
    
    if command_exists nginx; then
        print_info "Nginx already installed"
    else
        print_info "Installing Nginx..."
        apt install -y nginx >> "$LOG_FILE" 2>&1
    fi
    
    systemctl start nginx 2>/dev/null || true
    systemctl enable nginx 2>/dev/null || true
    print_success "Nginx ready"
}

# Create application user
create_app_user() {
    show_progress "Creating application user"
    
    if id "faithtracker" &>/dev/null; then
        print_info "User 'faithtracker' already exists"
    else
        useradd -m -s /bin/bash faithtracker >> "$LOG_FILE" 2>&1
        print_success "User 'faithtracker' created"
    fi
}

# Setup application directory
setup_app_directory() {
    show_progress "Setting up application directory"
    
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Directory $INSTALL_DIR already exists"
        echo ""
        read -p "Remove and reinstall? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing existing directory..."
            rm -rf "$INSTALL_DIR"
        else
            print_error "Installation cancelled. Please remove $INSTALL_DIR manually or choose a different location."
            exit 1
        fi
    fi
    
    mkdir -p "$INSTALL_DIR"
    
    # Check if running from within the repo
    if [ -f "$PWD/backend/server.py" ] && [ -f "$PWD/frontend/package.json" ]; then
        print_info "Copying application files from current directory..."
        rsync -a --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='build' . "$INSTALL_DIR/" >> "$LOG_FILE" 2>&1
        print_success "Application files copied"
    else
        print_error "Not running from repository directory"
        print_error "Please run this script from within the cloned FaithTracker repository"
        exit 1
    fi
    
    chown -R faithtracker:faithtracker "$INSTALL_DIR"
}

# Configure environment
configure_environment() {
    show_progress "Configuring application"
    
    # Initialize variables
    DOMAIN_NAME=""
    ADMIN_EMAIL=""
    ADMIN_PASSWORD=""
    ADMIN_PASSWORD_CONFIRM=""
    
    # Generate JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║    FaithTracker Configuration         ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
    echo ""
    
    # MongoDB URL
    if [ "$MONGODB_REMOTE" = true ]; then
        echo -e "${YELLOW}Enter your MongoDB connection string${NC}"
        echo "Example: mongodb+srv://user:pass@cluster.mongodb.net/dbname"
        while [ -z "$MONGO_URL" ]; do
            read -p "MongoDB URL: " MONGO_URL
            if [ -z "$MONGO_URL" ]; then
                print_error "MongoDB URL cannot be empty"
            fi
        done
    else
        MONGO_URL="mongodb://localhost:27017"
        print_info "Using local MongoDB: $MONGO_URL"
    fi
    
    # Database name
    echo ""
    read -p "Database name [pastoral_care_db]: " DB_NAME
    DB_NAME=${DB_NAME:-pastoral_care_db}
    
    # Domain name
    echo ""
    echo -e "${YELLOW}Enter your domain name (without http/https)${NC}"
    echo "Example: faithtracker.com or church.example.org"
    while [ -z "$DOMAIN_NAME" ]; do
        read -p "Domain: " DOMAIN_NAME
        if [ -z "$DOMAIN_NAME" ]; then
            print_error "Domain name cannot be empty"
        fi
    done
    
    # Church name (will be used as first campus name)
    echo ""
    echo -e "${YELLOW}First Campus Information${NC}"
    read -p "Campus name [GKBJ Main Campus]: " CAMPUS_NAME
    CAMPUS_NAME=${CAMPUS_NAME:-"GKBJ Main Campus"}
    
    read -p "Campus location/address: " CAMPUS_LOCATION
    CAMPUS_LOCATION=${CAMPUS_LOCATION:-"Jakarta, Indonesia"}
    
    echo "Select timezone:"
    echo "  1) Asia/Jakarta (UTC+7)"
    echo "  2) Asia/Singapore (UTC+8)"
    echo "  3) Asia/Tokyo (UTC+9)"
    read -p "Choice [1]: " TZ_CHOICE
    TZ_CHOICE=${TZ_CHOICE:-1}
    
    case $TZ_CHOICE in
        1) CAMPUS_TIMEZONE="Asia/Jakarta" ;;
        2) CAMPUS_TIMEZONE="Asia/Singapore" ;;
        3) CAMPUS_TIMEZONE="Asia/Tokyo" ;;
        *) CAMPUS_TIMEZONE="Asia/Jakarta" ;;
    esac
    
    # WhatsApp (optional)
    echo ""
    echo -e "${CYAN}WhatsApp integration (optional)${NC}"
    read -p "WhatsApp gateway URL (or press Enter to skip): " WHATSAPP_URL
    
    # Admin credentials
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║    Create Admin Account                ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
    echo ""
    
    while [ -z "$ADMIN_EMAIL" ]; do
        read -p "Admin email: " ADMIN_EMAIL
        if [ -z "$ADMIN_EMAIL" ]; then
            print_error "Email cannot be empty"
        elif ! validate_email "$ADMIN_EMAIL"; then
            print_error "Invalid email format"
            ADMIN_EMAIL=""
        fi
    done
    
    while [ -z "$ADMIN_PASSWORD" ] || [ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]; do
        read -s -p "Admin password (min 8 chars): " ADMIN_PASSWORD
        echo ""
        
        if [ ${#ADMIN_PASSWORD} -lt 8 ]; then
            print_error "Password must be at least 8 characters"
            ADMIN_PASSWORD=""
            continue
        fi
        
        read -s -p "Confirm password: " ADMIN_PASSWORD_CONFIRM
        echo ""
        
        if [ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]; then
            print_error "Passwords do not match"
            ADMIN_PASSWORD=""
        fi
    done
    
    # Show summary
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║    Configuration Summary               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo -e "  MongoDB:       ${CYAN}$MONGO_URL${NC}"
    echo -e "  Database:      ${CYAN}$DB_NAME${NC}"
    echo -e "  Domain:        ${CYAN}$DOMAIN_NAME${NC}"
    echo -e "  Church:        ${CYAN}$CHURCH_NAME${NC}"
    echo -e "  Admin:         ${CYAN}$ADMIN_EMAIL${NC}"
    echo ""
    read -p "Proceed with installation? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Installation cancelled"
        exit 1
    fi
    
    # Create backend .env
    cat > "$INSTALL_DIR/backend/.env" << EOF
MONGO_URL="$MONGO_URL"
DB_NAME="$DB_NAME"
CORS_ORIGINS="https://$DOMAIN_NAME"
JWT_SECRET_KEY="$JWT_SECRET"
CHURCH_NAME="$CHURCH_NAME"
WHATSAPP_GATEWAY_URL="$WHATSAPP_URL"
EOF
    
    # Create frontend .env
    cat > "$INSTALL_DIR/frontend/.env" << EOF
REACT_APP_BACKEND_URL="https://$DOMAIN_NAME"
WDS_SOCKET_PORT=443
REACT_APP_ENABLE_VISUAL_EDITS=false
ENABLE_HEALTH_CHECK=false
EOF
    
    chown faithtracker:faithtracker "$INSTALL_DIR/backend/.env"
    chown faithtracker:faithtracker "$INSTALL_DIR/frontend/.env"
    
    print_success "Configuration complete"
}

# Setup backend
setup_backend() {
    show_progress "Setting up backend (Python)"
    
    cd "$INSTALL_DIR/backend"
    
    print_info "Creating Python virtual environment..."
    sudo -u faithtracker python3 -m venv venv >> "$LOG_FILE" 2>&1
    
    print_info "Installing Python dependencies (may take 5-10 minutes)..."
    {
        sudo -u faithtracker "$INSTALL_DIR/backend/venv/bin/pip" install --upgrade pip
        sudo -u faithtracker "$INSTALL_DIR/backend/venv/bin/pip" install -r requirements.txt
    } >> "$LOG_FILE" 2>&1
    
    print_info "Creating database indexes..."
    sudo -u faithtracker "$INSTALL_DIR/backend/venv/bin/python" create_indexes.py >> "$LOG_FILE" 2>&1 || true
    
    print_info "Creating admin user..."
    sudo -u faithtracker "$INSTALL_DIR/backend/venv/bin/python" - << PYTHON_SCRIPT >> "$LOG_FILE" 2>&1
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

mongo_url = "$MONGO_URL"
db_name = "$DB_NAME"
admin_email = "$ADMIN_EMAIL"
admin_password = "$ADMIN_PASSWORD"

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin():
    user = {
        "email": admin_email,
        "password_hash": pwd_context.hash(admin_password),
        "name": "Administrator",
        "role": "full_admin",
        "church_id": None
    }
    
    existing = await db.users.find_one({"email": user["email"]})
    if existing:
        print("Admin user already exists")
    else:
        await db.users.insert_one(user)
        print(f"Admin user created: {user['email']}")

asyncio.run(create_admin())
PYTHON_SCRIPT
    
    print_success "Backend setup complete"
}

# Setup frontend
setup_frontend() {
    show_progress "Setting up frontend (React)"
    
    cd "$INSTALL_DIR/frontend"
    
    print_info "Installing Node.js dependencies (may take 5-10 minutes)..."
    sudo -u faithtracker yarn install >> "$LOG_FILE" 2>&1
    
    print_info "Building production bundle..."
    sudo -u faithtracker yarn build >> "$LOG_FILE" 2>&1
    
    print_success "Frontend setup complete"
}

# Create systemd service
create_systemd_service() {
    show_progress "Creating system service"
    
    cat > /etc/systemd/system/faithtracker-backend.service << 'EOF'
[Unit]
Description=FaithTracker FastAPI Backend
After=network.target mongod.service

[Service]
Type=simple
User=faithtracker
Group=faithtracker
WorkingDirectory=/opt/faithtracker/backend
Environment="PATH=/opt/faithtracker/backend/venv/bin"
ExecStart=/opt/faithtracker/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001 --workers 4
Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=faithtracker-backend

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable faithtracker-backend >> "$LOG_FILE" 2>&1
    systemctl start faithtracker-backend
    
    sleep 3
    
    if systemctl is-active --quiet faithtracker-backend; then
        print_success "Backend service started"
    else
        print_error "Backend service failed to start"
        echo "Check logs: sudo journalctl -u faithtracker-backend -n 50"
        exit 1
    fi
}

# Configure Nginx
configure_nginx() {
    show_progress "Configuring web server"
    
    cat > /etc/nginx/sites-available/faithtracker << EOF
server {
    listen 80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;

    root /opt/faithtracker/frontend/build;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /uploads/ {
        alias /opt/faithtracker/backend/uploads/;
        expires 30d;
        add_header Cache-Control "public";
    }

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 10M;
}
EOF
    
    ln -sf /etc/nginx/sites-available/faithtracker /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    nginx -t >> "$LOG_FILE" 2>&1
    systemctl restart nginx
    
    print_success "Nginx configured"
}

# Setup SSL
setup_ssl() {
    show_progress "Setting up SSL certificate"
    
    if ! command_exists certbot; then
        apt install -y certbot python3-certbot-nginx >> "$LOG_FILE" 2>&1
    fi
    
    echo ""
    echo -e "${YELLOW}SSL Certificate Setup${NC}"
    echo "This requires your domain to be pointing to this server's IP"
    echo ""
    read -p "Install SSL certificate now? (y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        certbot --nginx -d "$DOMAIN_NAME" -d "www.$DOMAIN_NAME" --non-interactive --agree-tos --email "$ADMIN_EMAIL" --redirect >> "$LOG_FILE" 2>&1 && \
        print_success "SSL certificate installed" || \
        print_warning "SSL setup incomplete. Run manually: sudo certbot --nginx"
    else
        print_info "Skipping SSL. Run later: sudo certbot --nginx"
    fi
}

# Run smoke tests
run_smoke_tests() {
    show_progress "Running system tests"
    
    sleep 2
    
    # Test backend
    if curl -sf http://localhost:8001/api/config/all > /dev/null; then
        print_success "Backend API responding"
    else
        print_warning "Backend API test failed"
    fi
    
    # Test frontend files
    if [ -f "$INSTALL_DIR/frontend/build/index.html" ]; then
        print_success "Frontend build verified"
    else
        print_warning "Frontend build missing"
    fi
    
    # Test Nginx
    if curl -sf http://localhost/ > /dev/null; then
        print_success "Web server responding"
    else
        print_warning "Web server test failed"
    fi
}

# Print final summary
print_summary() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                        ║${NC}"
    echo -e "${GREEN}║    ✓ FaithTracker Installation Complete!              ║${NC}"
    echo -e "${GREEN}║                                                        ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}🌐 Access your application:${NC}"
    echo -e "   http://$DOMAIN_NAME"
    echo ""
    echo -e "${CYAN}👤 Admin Login:${NC}"
    echo -e "   Email:    $ADMIN_EMAIL"
    echo -e "   Password: [as entered]"
    echo ""
    echo -e "${CYAN}📁 Important Locations:${NC}"
    echo -e "   App:      /opt/faithtracker"
    echo -e "   Logs:     $LOG_FILE"
    echo -e "   Backend:  sudo journalctl -u faithtracker-backend -f"
    echo ""
    echo -e "${CYAN}🔧 Manage Services:${NC}"
    echo -e "   Backend:  sudo systemctl status faithtracker-backend"
    echo -e "   Nginx:    sudo systemctl status nginx"
    echo -e "   MongoDB:  sudo systemctl status mongod"
    echo ""
    echo -e "${CYAN}📚 Documentation:${NC}"
    echo -e "   /opt/faithtracker/docs/FEATURES.md"
    echo -e "   /opt/faithtracker/docs/API.md"
    echo ""
    echo -e "${GREEN}Thank you for installing FaithTracker! 🙏${NC}"
    echo ""
}

#################################################################################
# MAIN INSTALLATION FLOW
#################################################################################

main() {
    clear
    
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                                                        ║"
    echo "║          FaithTracker Automated Installer              ║"
    echo "║                                                        ║"
    echo "║     Multi-Campus Pastoral Care Management System      ║"
    echo "║                                                        ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "This will install FaithTracker on your server."
    echo "Installation typically takes 10-15 minutes."
    echo ""
    echo -e "${YELLOW}Requirements:${NC}"
    echo "  • Fresh Debian 12 or Ubuntu 20.04+ server"
    echo "  • At least 2GB RAM"
    echo "  • Internet connection"
    echo "  • Domain name (optional but recommended)"
    echo ""
    read -p "Press Enter to begin installation or Ctrl+C to cancel..."
    
    # Run all installation steps
    check_root
    detect_os
    update_system
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
    setup_ssl
    run_smoke_tests
    
    # Show final summary
    print_summary
    
    echo "Installation log saved to: $LOG_FILE" >> "$LOG_FILE"
}

# Run main installation
main "$@"
