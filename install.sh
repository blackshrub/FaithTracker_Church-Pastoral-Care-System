#!/bin/bash

#################################################################################
# FaithTracker - Automated Installation Script for Debian 12/Ubuntu 20.04+
#################################################################################
#
# This script automates the complete installation and configuration of
# FaithTracker on a fresh Debian/Ubuntu server.
#
# Usage:
#   sudo ./install.sh
#
# Or one-liner from GitHub:
#   wget https://raw.githubusercontent.com/YOUR-USERNAME/faithtracker/main/install.sh -O install.sh && chmod +x install.sh && sudo ./install.sh
#
#################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="/var/log/faithtracker_install.log"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
       print_error "This script must be run as root or with sudo"
       exit 1
    fi
}

# Function to detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        print_error "Cannot detect OS. This script supports Debian 12 and Ubuntu 20.04+"
        exit 1
    fi

    print_info "Detected OS: $OS $VER"
    
    if [[ "$OS" != "debian" && "$OS" != "ubuntu" ]]; then
        print_error "Unsupported OS. This script only supports Debian and Ubuntu."
        exit 1
    fi
}

# Function to update system
update_system() {
    print_info "Updating system packages..."
    apt update >> "$LOG_FILE" 2>&1
    apt upgrade -y >> "$LOG_FILE" 2>&1
    apt install -y build-essential curl wget git >> "$LOG_FILE" 2>&1
    print_success "System updated successfully"
}

# Function to install Python
install_python() {
    print_info "Checking Python installation..."
    
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_info "Python $PYTHON_VERSION is already installed"
    else
        print_info "Installing Python 3..."
        apt install -y python3 python3-pip python3-venv python3-dev >> "$LOG_FILE" 2>&1
        print_success "Python installed successfully"
    fi
}

# Function to install Node.js & Yarn
install_nodejs() {
    print_info "Checking Node.js installation..."
    
    if command_exists node; then
        NODE_VERSION=$(node --version)
        print_info "Node.js $NODE_VERSION is already installed"
    else
        print_info "Installing Node.js 18.x LTS..."
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash - >> "$LOG_FILE" 2>&1
        apt install -y nodejs >> "$LOG_FILE" 2>&1
        print_success "Node.js installed successfully"
    fi
    
    if command_exists yarn; then
        print_info "Yarn is already installed"
    else
        print_info "Installing Yarn..."
        npm install -g yarn >> "$LOG_FILE" 2>&1
        print_success "Yarn installed successfully"
    fi
}

# Function to install MongoDB
install_mongodb() {
    print_info "Checking MongoDB installation..."
    
    if command_exists mongod; then
        print_info "MongoDB is already installed"
        systemctl start mongod || true
        systemctl enable mongod || true
    else
        print_warning "MongoDB not found. Do you want to install MongoDB locally?"
        read -p "Install MongoDB locally? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installing MongoDB..."
            
            # Import MongoDB GPG key
            curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg >> "$LOG_FILE" 2>&1
            
            # Add MongoDB repository
            if [[ "$OS" == "debian" ]]; then
                echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] http://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list >> "$LOG_FILE"
            else
                echo "deb [signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg] http://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list >> "$LOG_FILE"
            fi
            
            apt update >> "$LOG_FILE" 2>&1
            apt install -y mongodb-org >> "$LOG_FILE" 2>&1
            
            systemctl start mongod
            systemctl enable mongod
            
            print_success "MongoDB installed successfully"
        else
            print_warning "Skipping local MongoDB installation. You must provide a remote MongoDB connection string."
            MONGODB_REMOTE=true
        fi
    fi
}

# Function to install Nginx
install_nginx() {
    print_info "Checking Nginx installation..."
    
    if command_exists nginx; then
        print_info "Nginx is already installed"
    else
        print_info "Installing Nginx..."
        apt install -y nginx >> "$LOG_FILE" 2>&1
        systemctl start nginx
        systemctl enable nginx
        print_success "Nginx installed successfully"
    fi
}

# Function to install Supervisor
install_supervisor() {
    print_info "Checking Supervisor installation..."
    
    if command_exists supervisorctl; then
        print_info "Supervisor is already installed"
    else
        print_info "Installing Supervisor..."
        apt install -y supervisor >> "$LOG_FILE" 2>&1
        systemctl start supervisor
        systemctl enable supervisor
        print_success "Supervisor installed successfully"
    fi
}

# Function to create application user
create_app_user() {
    if id "faithtracker" &>/dev/null; then
        print_info "User 'faithtracker' already exists"
    else
        print_info "Creating application user 'faithtracker'..."
        useradd -m -s /bin/bash faithtracker >> "$LOG_FILE" 2>&1
        print_success "User 'faithtracker' created"
    fi
}

# Function to clone repository
clone_repository() {
    INSTALL_DIR="/opt/faithtracker"
    
    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Directory $INSTALL_DIR already exists"
        read -p "Remove and re-clone? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            print_error "Installation directory exists. Aborting."
            exit 1
        fi
    fi
    
    print_info "Cloning FaithTracker repository..."
    mkdir -p "$INSTALL_DIR"
    
    # For now, we'll copy files from current directory since we're already in the repo
    # In production, replace with: git clone https://github.com/YOUR-USERNAME/faithtracker.git "$INSTALL_DIR"
    
    if [ "$PWD" != "$INSTALL_DIR" ]; then
        cp -r . "$INSTALL_DIR"
    fi
    
    chown -R faithtracker:faithtracker "$INSTALL_DIR"
    print_success "Repository cloned to $INSTALL_DIR"
}

# Function to configure environment variables
configure_env() {
    print_info "Configuring environment variables..."
    
    # Generate JWT secret
    JWT_SECRET=$(openssl rand -hex 32)
    
    # Prompt for configuration
    echo ""
    echo -e "${YELLOW}=== Configuration ===${NC}"
    echo ""
    
    # MongoDB URL
    if [ "$MONGODB_REMOTE" = true ]; then
        read -p "Enter MongoDB connection string: " MONGO_URL
    else
        MONGO_URL="mongodb://localhost:27017"
        print_info "Using local MongoDB: $MONGO_URL"
    fi
    
    # Database name
    read -p "Enter database name [pastoral_care_db]: " DB_NAME
    DB_NAME=${DB_NAME:-pastoral_care_db}
    
    # Domain name
    read -p "Enter your domain name (e.g., faithtracker.com): " DOMAIN_NAME
    
    # Church name
    read -p "Enter church name [GKBJ]: " CHURCH_NAME
    CHURCH_NAME=${CHURCH_NAME:-GKBJ}
    
    # WhatsApp Gateway (optional)
    read -p "Enter WhatsApp gateway URL (leave blank to skip): " WHATSAPP_URL
    
    # Admin credentials
    echo ""
    echo -e "${YELLOW}=== Admin User Creation ===${NC}"
    read -p "Enter admin email: " ADMIN_EMAIL
    read -s -p "Enter admin password: " ADMIN_PASSWORD
    echo ""
    read -s -p "Confirm admin password: " ADMIN_PASSWORD_CONFIRM
    echo ""
    
    if [ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]; then
        print_error "Passwords do not match. Aborting."
        exit 1
    fi
    
    # Backend .env
    cat > /opt/faithtracker/backend/.env << EOF
MONGO_URL="$MONGO_URL"
DB_NAME="$DB_NAME"
CORS_ORIGINS="https://$DOMAIN_NAME"
JWT_SECRET_KEY="$JWT_SECRET"
CHURCH_NAME="$CHURCH_NAME"
WHATSAPP_GATEWAY_URL="$WHATSAPP_URL"
EOF
    
    # Frontend .env
    cat > /opt/faithtracker/frontend/.env << EOF
REACT_APP_BACKEND_URL="https://$DOMAIN_NAME"
WDS_SOCKET_PORT=443
REACT_APP_ENABLE_VISUAL_EDITS=false
ENABLE_HEALTH_CHECK=false
EOF
    
    chown faithtracker:faithtracker /opt/faithtracker/backend/.env
    chown faithtracker:faithtracker /opt/faithtracker/frontend/.env
    
    print_success "Environment variables configured"
}

# Function to setup backend
setup_backend() {
    print_info "Setting up backend..."
    
    cd /opt/faithtracker/backend
    
    # Create virtual environment
    print_info "Creating Python virtual environment..."
    sudo -u faithtracker python3 -m venv venv >> "$LOG_FILE" 2>&1
    
    # Install dependencies
    print_info "Installing Python dependencies (this may take a few minutes)..."
    sudo -u faithtracker /opt/faithtracker/backend/venv/bin/pip install --upgrade pip >> "$LOG_FILE" 2>&1
    sudo -u faithtracker /opt/faithtracker/backend/venv/bin/pip install -r requirements.txt >> "$LOG_FILE" 2>&1
    
    # Create MongoDB indexes
    print_info "Creating MongoDB indexes..."
    sudo -u faithtracker /opt/faithtracker/backend/venv/bin/python create_indexes.py >> "$LOG_FILE" 2>&1 || true
    
    # Create admin user
    print_info "Creating admin user..."
    sudo -u faithtracker /opt/faithtracker/backend/venv/bin/python - << PYTHON_SCRIPT
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
import os

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

# Function to setup frontend
setup_frontend() {
    print_info "Setting up frontend..."
    
    cd /opt/faithtracker/frontend
    
    # Install dependencies
    print_info "Installing Node.js dependencies (this may take several minutes)..."
    sudo -u faithtracker yarn install >> "$LOG_FILE" 2>&1
    
    # Build frontend
    print_info "Building React app for production..."
    sudo -u faithtracker yarn build >> "$LOG_FILE" 2>&1
    
    print_success "Frontend setup complete"
}

# Function to create systemd service
create_systemd_service() {
    print_info "Creating systemd service for backend..."
    
    cat > /etc/systemd/system/faithtracker-backend.service << 'EOF'
[Unit]
Description=FaithTracker FastAPI Backend
After=network.target mongod.service
Requires=mongod.service

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
    systemctl enable faithtracker-backend
    systemctl start faithtracker-backend
    
    sleep 3
    
    if systemctl is-active --quiet faithtracker-backend; then
        print_success "Backend service started successfully"
    else
        print_error "Backend service failed to start. Check logs: sudo journalctl -u faithtracker-backend"
        exit 1
    fi
}

# Function to configure Nginx
configure_nginx() {
    print_info "Configuring Nginx..."
    
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
    
    # Enable site
    ln -sf /etc/nginx/sites-available/faithtracker /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    nginx -t >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        systemctl restart nginx
        print_success "Nginx configured successfully"
    else
        print_error "Nginx configuration test failed. Check logs."
        exit 1
    fi
}

# Function to setup SSL with Let's Encrypt
setup_ssl() {
    print_info "Setting up SSL with Let's Encrypt..."
    
    if ! command_exists certbot; then
        print_info "Installing Certbot..."
        apt install -y certbot python3-certbot-nginx >> "$LOG_FILE" 2>&1
    fi
    
    read -p "Install SSL certificate now? (requires valid DNS) (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Obtaining SSL certificate..."
        certbot --nginx -d "$DOMAIN_NAME" -d "www.$DOMAIN_NAME" --non-interactive --agree-tos --email "$ADMIN_EMAIL" --redirect >> "$LOG_FILE" 2>&1
        
        if [ $? -eq 0 ]; then
            print_success "SSL certificate installed successfully"
        else
            print_warning "SSL certificate installation failed. You can run 'sudo certbot --nginx' manually later."
        fi
    else
        print_warning "Skipping SSL setup. You can run 'sudo certbot --nginx' later."
    fi
}

# Function to configure firewall
configure_firewall() {
    if command_exists ufw; then
        print_info "Configuring firewall..."
        ufw allow ssh >> "$LOG_FILE" 2>&1
        ufw allow 80/tcp >> "$LOG_FILE" 2>&1
        ufw allow 443/tcp >> "$LOG_FILE" 2>&1
        echo "y" | ufw enable >> "$LOG_FILE" 2>&1
        print_success "Firewall configured"
    else
        print_warning "UFW not found. Skipping firewall configuration."
    fi
}

# Function to run smoke tests
run_smoke_tests() {
    print_info "Running smoke tests..."
    
    # Test backend API
    sleep 2
    API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/config/all)
    
    if [ "$API_RESPONSE" -eq 200 ]; then
        print_success "Backend API is responding (HTTP $API_RESPONSE)"
    else
        print_error "Backend API test failed (HTTP $API_RESPONSE)"
    fi
    
    # Test frontend
    if [ -f /opt/faithtracker/frontend/build/index.html ]; then
        print_success "Frontend build exists"
    else
        print_error "Frontend build not found"
    fi
    
    # Test Nginx
    NGINX_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/)
    
    if [ "$NGINX_RESPONSE" -eq 200 ] || [ "$NGINX_RESPONSE" -eq 301 ]; then
        print_success "Nginx is serving the application (HTTP $NGINX_RESPONSE)"
    else
        print_warning "Nginx test returned HTTP $NGINX_RESPONSE"
    fi
}

# Function to print summary
print_summary() {
    echo ""
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${GREEN}  FaithTracker Installation Complete!${NC}"
    echo -e "${GREEN}=====================================${NC}"
    echo ""
    echo -e "${BLUE}Access your application at:${NC}"
    echo -e "  ${GREEN}http://$DOMAIN_NAME${NC} (or https:// if SSL was configured)"
    echo ""
    echo -e "${BLUE}Admin Credentials:${NC}"
    echo -e "  Email:    ${GREEN}$ADMIN_EMAIL${NC}"
    echo -e "  Password: ${GREEN}[As entered during installation]${NC}"
    echo ""
    echo -e "${BLUE}Important Directories:${NC}"
    echo -e "  Application: ${GREEN}/opt/faithtracker/${NC}"
    echo -e "  Backend:     ${GREEN}/opt/faithtracker/backend/${NC}"
    echo -e "  Frontend:    ${GREEN}/opt/faithtracker/frontend/${NC}"
    echo ""
    echo -e "${BLUE}Service Management:${NC}"
    echo -e "  Backend:  ${GREEN}sudo systemctl status faithtracker-backend${NC}"
    echo -e "  Nginx:    ${GREEN}sudo systemctl status nginx${NC}"
    echo -e "  MongoDB:  ${GREEN}sudo systemctl status mongod${NC}"
    echo ""
    echo -e "${BLUE}Logs:${NC}"
    echo -e "  Backend:  ${GREEN}sudo journalctl -u faithtracker-backend -f${NC}"
    echo -e "  Nginx:    ${GREEN}sudo tail -f /var/log/nginx/error.log${NC}"
    echo -e "  Install:  ${GREEN}$LOG_FILE${NC}"
    echo ""
    echo -e "${BLUE}Next Steps:${NC}"
    echo -e "  1. Log in at ${GREEN}http://$DOMAIN_NAME${NC}"
    echo -e "  2. Configure your first campus in Settings"
    echo -e "  3. Add church members"
    echo -e "  4. Start managing pastoral care!"
    echo ""
    echo -e "${YELLOW}Documentation:${NC}"
    echo -e "  Features:    ${GREEN}/opt/faithtracker/docs/FEATURES.md${NC}"
    echo -e "  API Docs:    ${GREEN}/opt/faithtracker/docs/API.md${NC}"
    echo -e "  Deployment:  ${GREEN}/opt/faithtracker/docs/DEPLOYMENT_DEBIAN.md${NC}"
    echo ""
    echo -e "${GREEN}Thank you for installing FaithTracker! \u2764\ufe0f${NC}"
    echo ""
}

# Main installation flow
main() {
    clear
    echo -e "${BLUE}=====================================${NC}"
    echo -e "${BLUE}  FaithTracker Automated Installer${NC}"
    echo -e "${BLUE}=====================================${NC}"
    echo ""
    echo "This script will install FaithTracker on your server."
    echo "Installation log: $LOG_FILE"
    echo ""
    read -p "Press Enter to continue or Ctrl+C to abort..."
    
    # Start logging
    echo "FaithTracker Installation started at $(date)" > "$LOG_FILE"
    
    # Run installation steps
    check_root
    detect_os
    update_system
    install_python
    install_nodejs
    install_mongodb
    install_nginx
    install_supervisor
    create_app_user
    clone_repository
    configure_env
    setup_backend
    setup_frontend
    create_systemd_service
    configure_nginx
    setup_ssl
    configure_firewall
    run_smoke_tests
    
    # Print summary
    print_summary
    
    echo "Installation completed at $(date)" >> "$LOG_FILE"
}

# Run main function
main "$@"
