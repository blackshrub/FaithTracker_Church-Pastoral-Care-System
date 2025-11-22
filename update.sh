#!/bin/bash

#################################################################################
# FaithTracker Smart Update Script
# Intelligently detects changes and updates only what's needed
# Perfect for non-technical users with delightful feedback!
#################################################################################

set -e

# Colors for delightful output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# Emojis for extra delight
ROCKET="🚀"
SPARKLES="✨"
PACKAGE="📦"
WRENCH="🔧"
DATABASE="🗄️"
WEB="🌐"
CHECK="✓"
CLOCK="⏱️"
CELEBRATE="🎉"
THINKING="🤔"
EYES="👀"

# Configuration
GIT_DIR=$(pwd)
APP_DIR="/opt/faithtracker"
LOG_FILE="/var/log/faithtracker_update.log"

# Create log file
echo "=== FaithTracker Update started at $(date) ===" >> "$LOG_FILE" 2>&1 || LOG_FILE="/tmp/faithtracker_update.log"

#################################################################################
# HELPER FUNCTIONS
#################################################################################

print_header() {
    clear
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                            ║${NC}"
    echo -e "${CYAN}║  ${SPARKLES}  ${BOLD}FaithTracker Smart Update System${NC}${CYAN}  ${SPARKLES}               ║${NC}"
    echo -e "${CYAN}║                                                            ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${MAGENTA}${BOLD}$1${NC}"
    echo -e "${MAGENTA}$(printf '─%.0s' {1..60})${NC}"
}

print_step() {
    echo -e "${BLUE}${ROCKET}${NC} $1..."
}

print_success() {
    echo -e "   ${GREEN}${CHECK}${NC} $1"
}

print_info() {
    echo -e "   ${CYAN}ℹ${NC}  $1"
}

print_warning() {
    echo -e "   ${YELLOW}⚠${NC}  $1"
}

print_error() {
    echo -e "   ${RED}✗${NC} $1"
}

print_thinking() {
    echo -e "${THINKING} $1..."
}

# Progress bar animation
show_progress() {
    local duration=$1
    local message=$2
    echo -n "   ${CYAN}${CLOCK}${NC} $message "

    for i in $(seq 1 $duration); do
        echo -n "."
        sleep 1
    done

    echo -e " ${GREEN}Done!${NC}"
}

#################################################################################
# VALIDATION FUNCTIONS
#################################################################################

check_prerequisites() {
    print_section "${EYES} Checking Prerequisites"

    # Check if running from git repository
    if [ ! -f "$GIT_DIR/backend/server.py" ]; then
        print_error "Not in FaithTracker git repository"
        print_info "Please run this script from the cloned repository directory"
        exit 1
    fi
    print_success "Running from git repository"

    # Check if app directory exists
    if [ ! -d "$APP_DIR" ]; then
        print_error "Application directory $APP_DIR not found"
        print_info "Please run install.sh first"
        exit 1
    fi
    print_success "Application directory found"

    # Check if we have sudo access
    if ! sudo -n true 2>/dev/null; then
        print_warning "You may need to enter your password for system operations"
    fi
    print_success "All prerequisites met"
}

#################################################################################
# CHANGE DETECTION
#################################################################################

detect_changes() {
    print_section "${THINKING} Analyzing Changes"

    # Store current directory state before rsync
    cd "$GIT_DIR"

    # Get list of changed files (comparing git repo to deployed app)
    BACKEND_CHANGED=false
    FRONTEND_CHANGED=false

    print_thinking "Scanning for modified files"

    # Check backend changes
    if rsync -ain --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='build' --exclude='.env' "$GIT_DIR/backend/" "$APP_DIR/backend/" | grep -q "^>f"; then
        BACKEND_CHANGED=true
        BACKEND_FILE_COUNT=$(rsync -ain --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='build' --exclude='.env' "$GIT_DIR/backend/" "$APP_DIR/backend/" | grep "^>f" | wc -l | tr -d ' ')
        print_success "Backend changes detected: $BACKEND_FILE_COUNT file(s)"
    else
        print_info "No backend changes"
    fi

    # Check frontend changes
    if rsync -ain --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='build' --exclude='.env' "$GIT_DIR/frontend/" "$APP_DIR/frontend/" | grep -q "^>f"; then
        FRONTEND_CHANGED=true
        FRONTEND_FILE_COUNT=$(rsync -ain --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='build' --exclude='.env' "$GIT_DIR/frontend/" "$APP_DIR/frontend/" | grep "^>f" | wc -l | tr -d ' ')
        print_success "Frontend changes detected: $FRONTEND_FILE_COUNT file(s)"
    else
        print_info "No frontend changes"
    fi

    # Summary
    echo ""
    if [ "$BACKEND_CHANGED" = false ] && [ "$FRONTEND_CHANGED" = false ]; then
        echo -e "${GREEN}${CELEBRATE} Great news! Your application is already up to date!${NC}"
        echo ""
        print_info "No changes detected. Nothing to update."
        exit 0
    fi
}

show_update_plan() {
    print_section "${PACKAGE} Update Plan"

    echo -e "${BOLD}What will be updated:${NC}"
    echo ""

    TOTAL_STEPS=2  # Base steps: copy files, verify

    if [ "$BACKEND_CHANGED" = true ]; then
        echo -e "  ${BLUE}▶${NC} Backend API ($BACKEND_FILE_COUNT file(s))"
        echo -e "    • Install Python dependencies"
        echo -e "    • Run database migrations"
        echo -e "    • Restart backend service"
        TOTAL_STEPS=$((TOTAL_STEPS + 3))
    fi

    if [ "$FRONTEND_CHANGED" = true ]; then
        echo -e "  ${BLUE}▶${NC} Frontend UI ($FRONTEND_FILE_COUNT file(s))"
        echo -e "    • Install Node.js dependencies"
        echo -e "    • Build production bundle"
        echo -e "    • Restart web server"
        TOTAL_STEPS=$((TOTAL_STEPS + 3))
    fi

    echo ""

    # Time estimate
    ESTIMATED_TIME=1
    if [ "$BACKEND_CHANGED" = true ]; then
        ESTIMATED_TIME=$((ESTIMATED_TIME + 2))
    fi
    if [ "$FRONTEND_CHANGED" = true ]; then
        ESTIMATED_TIME=$((ESTIMATED_TIME + 5))
    fi

    print_info "Estimated time: ~${ESTIMATED_TIME} minutes"
    print_info "Total steps: $TOTAL_STEPS"

    echo ""
    echo -e "${YELLOW}${BOLD}Ready to proceed?${NC}"
    read -p "Continue with update? (y/n): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Update cancelled. No changes made.${NC}"
        exit 0
    fi
}

#################################################################################
# UPDATE FUNCTIONS
#################################################################################

copy_files() {
    print_section "${WRENCH} Copying Updated Files"

    print_step "Syncing files to application directory"
    rsync -a --exclude='.git' --exclude='node_modules' --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='build' --exclude='.env' "$GIT_DIR/" "$APP_DIR/" >> "$LOG_FILE" 2>&1
    print_success "Files synchronized"
}

update_backend() {
    print_section "${DATABASE} Updating Backend"

    cd "$APP_DIR/backend"

    # Check if venv exists
    if [ ! -d "venv" ]; then
        print_step "Creating Python virtual environment"
        python3 -m venv venv >> "$LOG_FILE" 2>&1
        print_success "Virtual environment created"
    fi

    # Update dependencies
    print_step "Installing Python dependencies"
    source venv/bin/activate
    pip install -r requirements.txt --quiet >> "$LOG_FILE" 2>&1
    print_success "Dependencies updated"

    # Run migrations
    print_step "Running database migrations"
    python migrate.py 2>&1 | tee -a "$LOG_FILE"
    MIGRATION_STATUS=${PIPESTATUS[0]}

    if [ $MIGRATION_STATUS -ne 0 ]; then
        print_error "Database migration failed!"
        print_warning "Check logs: cat $LOG_FILE"
        deactivate
        exit 1
    fi

    deactivate

    # Restart backend service
    print_step "Restarting backend service"
    sudo systemctl restart faithtracker-backend >> "$LOG_FILE" 2>&1
    sleep 2
    print_success "Backend service restarted"
}

update_frontend() {
    print_section "${WEB} Updating Frontend"

    cd "$APP_DIR/frontend"

    # Install dependencies
    print_step "Installing Node.js dependencies"
    yarn install --silent >> "$LOG_FILE" 2>&1
    print_success "Dependencies installed"

    # Build production bundle
    print_step "Building production bundle (this may take 3-5 minutes)"

    # Build with progress indication
    yarn build >> "$LOG_FILE" 2>&1 &
    BUILD_PID=$!

    # Show progress while building
    while kill -0 $BUILD_PID 2>/dev/null; do
        echo -n "."
        sleep 2
    done

    wait $BUILD_PID
    BUILD_STATUS=$?

    if [ $BUILD_STATUS -ne 0 ]; then
        echo ""
        print_error "Frontend build failed!"
        print_warning "Check logs: cat $LOG_FILE"
        exit 1
    fi

    echo ""
    print_success "Production bundle built"

    # Restart nginx
    print_step "Restarting web server"
    sudo systemctl restart nginx >> "$LOG_FILE" 2>&1
    print_success "Web server restarted"
}

verify_services() {
    print_section "${CHECK} Verifying Services"

    sleep 3

    # Check backend
    print_step "Checking backend API"
    BACKEND_STATUS=$(sudo systemctl is-active faithtracker-backend)
    if [ "$BACKEND_STATUS" = "active" ]; then
        print_success "Backend is running"
    else
        print_error "Backend is not running!"
        print_info "Check logs: sudo journalctl -u faithtracker-backend -n 50"
        exit 1
    fi

    # Check nginx
    print_step "Checking web server"
    NGINX_STATUS=$(sudo systemctl is-active nginx)
    if [ "$NGINX_STATUS" = "active" ]; then
        print_success "Web server is running"
    else
        print_error "Web server is not running!"
        print_info "Check logs: sudo systemctl status nginx"
        exit 1
    fi

    # Check API endpoint
    print_step "Testing API endpoint"
    if curl -sf http://localhost:8001/api/config/all > /dev/null 2>&1; then
        print_success "API is responding"
    else
        print_warning "API health check failed (may be starting up)"
    fi
}

print_completion() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                            ║${NC}"
    echo -e "${GREEN}║  ${CELEBRATE}  ${BOLD}Update Completed Successfully!${NC}${GREEN}  ${CELEBRATE}                    ║${NC}"
    echo -e "${GREEN}║                                                            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    print_info "Your FaithTracker system is now up to date!"
    echo ""

    echo -e "${CYAN}${BOLD}📝 Next Steps:${NC}"
    echo ""
    echo -e "  1. ${BOLD}Clear your browser cache${NC}"
    echo -e "     Press: ${YELLOW}Ctrl + Shift + R${NC} (Windows/Linux) or ${YELLOW}Cmd + Shift + R${NC} (Mac)"
    echo ""
    echo -e "  2. ${BOLD}Reload your website${NC}"
    echo -e "     Visit your FaithTracker URL and log in"
    echo ""
    echo -e "  3. ${BOLD}Test main features${NC}"
    echo -e "     • Dashboard loads correctly"
    echo -e "     • Member list displays"
    echo -e "     • Forms work as expected"
    echo ""

    if [ "$BACKEND_CHANGED" = true ]; then
        echo -e "${CYAN}${BOLD}🔍 Backend Logs:${NC}"
        echo -e "  View real-time logs: ${YELLOW}sudo journalctl -u faithtracker-backend -f${NC}"
        echo ""
    fi

    echo -e "${GREEN}${SPARKLES} Thank you for using FaithTracker! ${SPARKLES}${NC}"
    echo ""
}

#################################################################################
# MAIN EXECUTION
#################################################################################

main() {
    print_header

    # Validation
    check_prerequisites

    # Detect what changed
    detect_changes

    # Show update plan
    show_update_plan

    # Execute updates
    echo ""
    print_section "${ROCKET} Starting Update"

    copy_files

    if [ "$BACKEND_CHANGED" = true ]; then
        update_backend
    fi

    if [ "$FRONTEND_CHANGED" = true ]; then
        update_frontend
    fi

    verify_services

    # Success!
    print_completion
}

# Error handler
trap 'echo -e "\n${RED}Update failed!${NC} Check logs at: $LOG_FILE"; exit 1' ERR

# Run main
main "$@"
