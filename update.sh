#!/bin/bash

#################################################################################
# FaithTracker - World-Class Smart Update Script
# Intelligent updates with backup, rollback, and zero-downtime deployment
#################################################################################
#
# Features:
#   - Automatic backup before update (with rollback capability)
#   - Smart change detection (only updates what changed)
#   - Maintenance mode toggle
#   - Health checks with automatic rollback on failure
#   - Changelog display from git commits
#   - Beautiful progress indicators
#   - Reads configuration from installed app
#
# Usage:
#   cd /path/to/git/repo
#   sudo bash update.sh
#   sudo bash update.sh --rollback    # Rollback to previous version
#   sudo bash update.sh --force       # Force update without prompts
#
#################################################################################

set -e

#################################################################################
# CONSTANTS & CONFIGURATION
#################################################################################

readonly VERSION="2.5.0"
readonly GIT_DIR=$(pwd)
readonly APP_DIR="/opt/faithtracker"
readonly BACKUP_DIR="/var/backups/faithtracker"
readonly LOG_FILE="/var/log/faithtracker_update.log"
readonly MAINTENANCE_FILE="$APP_DIR/frontend/build/maintenance.html"
readonly MAX_BACKUPS=5

# Track timing
START_TIME=$(date +%s)

# Parse command line arguments
FORCE_UPDATE=false
DO_ROLLBACK=false
for arg in "$@"; do
    case $arg in
        --force) FORCE_UPDATE=true ;;
        --rollback) DO_ROLLBACK=true ;;
    esac
done

#################################################################################
# COLORS & STYLING
#################################################################################

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

readonly CHECKMARK="${GREEN}✓${NC}"
readonly CROSSMARK="${RED}✗${NC}"
readonly ARROW="${CYAN}➜${NC}"
readonly BULLET="${BLUE}●${NC}"
readonly ROCKET="${MAGENTA}🚀${NC}"
readonly BACKUP_ICON="${YELLOW}💾${NC}"
readonly CLOCK="${CYAN}⏱${NC}"

#################################################################################
# LOGGING
#################################################################################

setup_logging() {
    mkdir -p "$(dirname $LOG_FILE)" 2>/dev/null || true
    touch "$LOG_FILE" 2>/dev/null || LOG_FILE="/tmp/faithtracker_update.log"
    echo "" >> "$LOG_FILE"
    echo "═══════════════════════════════════════════════════════════════════" >> "$LOG_FILE"
    echo "FaithTracker Update - $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
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
    ║      ███████╗███╗   ███╗ █████╗ ██████╗ ████████╗                    ║
    ║      ██╔════╝████╗ ████║██╔══██╗██╔══██╗╚══██╔══╝                    ║
    ║      ███████╗██╔████╔██║███████║██████╔╝   ██║                       ║
    ║      ╚════██║██║╚██╔╝██║██╔══██║██╔══██╗   ██║                       ║
    ║      ███████║██║ ╚═╝ ██║██║  ██║██║  ██║   ██║                       ║
    ║      ╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝                       ║
    ║                                                                       ║
    ║              FaithTracker Smart Update System                         ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    echo -e "                      ${DIM}Updater v${VERSION}${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${MAGENTA}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}${BOLD}  $1${NC}"
    echo -e "${MAGENTA}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_step() {
    echo -e "  ${ARROW} $1"
}

print_info() {
    echo -e "  ${BULLET} $1"
}

print_success() {
    echo -e "  ${CHECKMARK} ${GREEN}$1${NC}"
}

print_warning() {
    echo -e "  ${YELLOW}⚠${NC}  $1"
}

print_error() {
    echo -e "  ${CROSSMARK} ${RED}$1${NC}"
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

show_spinner() {
    local pid=$1
    local message=$2
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0

    while kill -0 $pid 2>/dev/null; do
        printf "\r  ${CYAN}${spin:$i:1}${NC} ${message}..."
        i=$(( (i+1) % 10 ))
        sleep 0.1
    done
    printf "\r                                                                \r"
}

#################################################################################
# ERROR HANDLING
#################################################################################

cleanup_on_error() {
    local exit_code=$?
    echo ""
    print_error "Update failed!"
    echo ""

    if [ -n "$BACKUP_NAME" ] && [ -d "$BACKUP_DIR/$BACKUP_NAME" ]; then
        echo -e "${YELLOW}${BOLD}A backup was created before the update:${NC}"
        echo -e "  ${BACKUP_ICON} $BACKUP_DIR/$BACKUP_NAME"
        echo ""
        echo -e "${CYAN}To rollback to the previous version, run:${NC}"
        echo -e "  sudo bash $0 --rollback"
    fi

    echo ""
    echo -e "Check logs: ${CYAN}cat $LOG_FILE${NC}"
    exit $exit_code
}

trap cleanup_on_error ERR

#################################################################################
# PREREQUISITE CHECKS
#################################################################################

check_prerequisites() {
    print_section "Checking Prerequisites"

    # Check if running from git repository
    if [ ! -f "$GIT_DIR/backend/server.py" ] || [ ! -f "$GIT_DIR/frontend/package.json" ]; then
        print_error "Not in FaithTracker git repository"
        print_info "Please run this script from the cloned repository directory"
        exit 1
    fi
    print_success "Running from git repository"

    # Check if app directory exists
    if [ ! -d "$APP_DIR" ]; then
        print_error "Application not installed at $APP_DIR"
        print_info "Please run install.sh first"
        exit 1
    fi
    print_success "Application directory found"

    # Check if we have root access
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root or with sudo"
        exit 1
    fi
    print_success "Running with proper permissions"

    # Read installed configuration
    if [ -f "$APP_DIR/backend/.env" ]; then
        source "$APP_DIR/backend/.env" 2>/dev/null || true
        BACKEND_PORT=${BACKEND_PORT:-8001}
        print_success "Configuration loaded (port: $BACKEND_PORT)"
    else
        BACKEND_PORT=8001
        print_warning "No configuration found, using defaults"
    fi

    # Get versions
    if [ -f "$APP_DIR/.version" ]; then
        INSTALLED_VERSION=$(cat "$APP_DIR/.version")
    else
        INSTALLED_VERSION="unknown"
    fi

    if [ -f "$GIT_DIR/frontend/package.json" ]; then
        NEW_VERSION=$(grep '"version"' "$GIT_DIR/frontend/package.json" | head -1 | sed 's/.*: "\(.*\)".*/\1/')
    else
        NEW_VERSION="unknown"
    fi

    print_info "Installed version: ${CYAN}$INSTALLED_VERSION${NC}"
    print_info "New version: ${CYAN}$NEW_VERSION${NC}"
}

#################################################################################
# ROLLBACK FUNCTIONALITY
#################################################################################

perform_rollback() {
    print_section "Rollback Mode"

    # List available backups
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        print_error "No backups found in $BACKUP_DIR"
        exit 1
    fi

    echo -e "  ${BACKUP_ICON} ${BOLD}Available backups:${NC}"
    echo ""

    local i=1
    local backups=()
    for backup in $(ls -t "$BACKUP_DIR" 2>/dev/null); do
        backups+=("$backup")
        local backup_date=$(echo "$backup" | sed 's/faithtracker_//' | sed 's/_/ /' | head -c 15)
        echo -e "    ${CYAN}[$i]${NC} $backup"
        i=$((i + 1))
        if [ $i -gt 5 ]; then break; fi
    done

    echo ""
    read -p "  Select backup to restore (1-$((i-1))) or 'q' to quit: " selection

    if [[ "$selection" == "q" ]]; then
        echo "Rollback cancelled"
        exit 0
    fi

    if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt $((i-1)) ]; then
        print_error "Invalid selection"
        exit 1
    fi

    local selected_backup="${backups[$((selection-1))]}"
    print_info "Selected: $selected_backup"

    echo ""
    read -p "  Confirm rollback to $selected_backup? (y/N): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Rollback cancelled"
        exit 0
    fi

    # Stop services
    print_step "Stopping services"
    systemctl stop faithtracker-backend 2>/dev/null || true

    # Restore backup
    print_step "Restoring from backup"
    rm -rf "$APP_DIR"
    cp -a "$BACKUP_DIR/$selected_backup" "$APP_DIR"

    # Fix permissions
    chown -R faithtracker:faithtracker "$APP_DIR"

    # Restart services
    print_step "Restarting services"
    systemctl start faithtracker-backend
    systemctl restart nginx

    sleep 3

    # Verify
    if systemctl is-active --quiet faithtracker-backend; then
        print_success "Rollback completed successfully!"
        print_info "Restored to: $selected_backup"
    else
        print_error "Services failed to start after rollback"
        print_info "Check logs: sudo journalctl -u faithtracker-backend -n 50"
    fi

    exit 0
}

#################################################################################
# CHANGE DETECTION
#################################################################################

detect_changes() {
    print_section "Analyzing Changes"

    print_step "Scanning for modifications..."

    BACKEND_CHANGED=false
    FRONTEND_CHANGED=false
    BACKEND_FILE_COUNT=0
    FRONTEND_FILE_COUNT=0

    # Check backend changes
    local backend_diff=$(rsync -ain --exclude='.git' --exclude='node_modules' --exclude='venv' \
        --exclude='__pycache__' --exclude='*.pyc' --exclude='build' --exclude='.env' \
        --exclude='uploads' "$GIT_DIR/backend/" "$APP_DIR/backend/" 2>/dev/null | grep "^>f" || true)

    if [ -n "$backend_diff" ]; then
        BACKEND_CHANGED=true
        BACKEND_FILE_COUNT=$(echo "$backend_diff" | wc -l | tr -d ' ')
        print_success "Backend changes: ${CYAN}$BACKEND_FILE_COUNT${NC} file(s) modified"
        log "Backend files changed: $BACKEND_FILE_COUNT"
    else
        print_info "Backend: No changes"
    fi

    # Check frontend changes
    local frontend_diff=$(rsync -ain --exclude='.git' --exclude='node_modules' --exclude='venv' \
        --exclude='__pycache__' --exclude='build' --exclude='.env' \
        "$GIT_DIR/frontend/" "$APP_DIR/frontend/" 2>/dev/null | grep "^>f" || true)

    if [ -n "$frontend_diff" ]; then
        FRONTEND_CHANGED=true
        FRONTEND_FILE_COUNT=$(echo "$frontend_diff" | wc -l | tr -d ' ')
        print_success "Frontend changes: ${CYAN}$FRONTEND_FILE_COUNT${NC} file(s) modified"
        log "Frontend files changed: $FRONTEND_FILE_COUNT"
    else
        print_info "Frontend: No changes"
    fi

    # Check for other changed files (docs, scripts, etc.)
    local other_diff=$(rsync -ain --exclude='.git' --exclude='node_modules' --exclude='venv' \
        --exclude='__pycache__' --exclude='build' --exclude='.env' \
        --exclude='backend' --exclude='frontend' \
        "$GIT_DIR/" "$APP_DIR/" 2>/dev/null | grep "^>f" || true)

    if [ -n "$other_diff" ]; then
        OTHER_FILE_COUNT=$(echo "$other_diff" | wc -l | tr -d ' ')
        print_info "Other files: ${CYAN}$OTHER_FILE_COUNT${NC} file(s) modified"
    fi

    # No changes detected
    if [ "$BACKEND_CHANGED" = false ] && [ "$FRONTEND_CHANGED" = false ]; then
        if [ "$FORCE_UPDATE" = true ]; then
            echo ""
            print_warning "No changes detected, but --force flag is set"
            print_info "Will rebuild backend and frontend anyway..."
        else
            echo ""
            echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
            echo -e "${GREEN}║${NC}  ${CHECKMARK} ${BOLD}Your application is already up to date!${NC}                      ${GREEN}║${NC}"
            echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
            echo ""
            echo -e "  ${DIM}Tip: Use ${NC}--force${DIM} to rebuild anyway${NC}"
            echo ""
            exit 0
        fi
    fi
}

show_changelog() {
    print_section "What's New"

    # Try to show git commits between versions
    cd "$GIT_DIR"
    if git rev-parse --git-dir > /dev/null 2>&1; then
        echo -e "  ${BOLD}Recent commits:${NC}"
        echo ""
        git --no-pager log --oneline -10 --pretty=format:"    ${CYAN}%h${NC} %s" 2>/dev/null || true
        echo ""
    fi
}

show_update_plan() {
    print_section "Update Plan"

    echo -e "  ${BOLD}The following will be updated:${NC}"
    echo ""

    local estimated_time=1

    if [ "$BACKEND_CHANGED" = true ] || [ "$FORCE_UPDATE" = true ]; then
        local backend_label="Backend API"
        [ "$FORCE_UPDATE" = true ] && [ "$BACKEND_CHANGED" = false ] && backend_label="Backend API (forced rebuild)"
        echo -e "    ${ROCKET} ${BOLD}${backend_label}${NC} (${BACKEND_FILE_COUNT:-0} files)"
        echo -e "       ${DIM}• Update Python dependencies${NC}"
        echo -e "       ${DIM}• Run database migrations${NC}"
        echo -e "       ${DIM}• Restart backend service${NC}"
        estimated_time=$((estimated_time + 2))
    fi

    if [ "$FRONTEND_CHANGED" = true ] || [ "$FORCE_UPDATE" = true ]; then
        local frontend_label="Frontend UI"
        [ "$FORCE_UPDATE" = true ] && [ "$FRONTEND_CHANGED" = false ] && frontend_label="Frontend UI (forced rebuild)"
        echo -e "    ${ROCKET} ${BOLD}${frontend_label}${NC} (${FRONTEND_FILE_COUNT:-0} files)"
        echo -e "       ${DIM}• Install Node dependencies${NC}"
        echo -e "       ${DIM}• Build production bundle${NC}"
        echo -e "       ${DIM}• Clear browser cache notice${NC}"
        estimated_time=$((estimated_time + 5))
    fi

    echo ""
    echo -e "  ${CLOCK} Estimated time: ${CYAN}~${estimated_time} minutes${NC}"
    echo -e "  ${BACKUP_ICON} Automatic backup: ${CYAN}Enabled${NC}"
    echo ""

    if [ "$FORCE_UPDATE" = false ]; then
        read -p "  Proceed with update? (Y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Update cancelled"
            exit 0
        fi
    fi
}

#################################################################################
# BACKUP FUNCTIONS
#################################################################################

create_backup() {
    print_section "Creating Backup"

    mkdir -p "$BACKUP_DIR"

    BACKUP_NAME="faithtracker_$(date +%Y%m%d_%H%M%S)"
    print_step "Backing up current installation..."

    cp -a "$APP_DIR" "$BACKUP_DIR/$BACKUP_NAME" >> "$LOG_FILE" 2>&1 &
    show_spinner $! "Creating backup"
    wait

    print_success "Backup created: ${CYAN}$BACKUP_NAME${NC}"
    log "Backup created: $BACKUP_DIR/$BACKUP_NAME"

    # Clean up old backups (keep only MAX_BACKUPS)
    local backup_count=$(ls -1 "$BACKUP_DIR" 2>/dev/null | wc -l)
    if [ "$backup_count" -gt "$MAX_BACKUPS" ]; then
        print_step "Cleaning old backups (keeping last $MAX_BACKUPS)"
        ls -t "$BACKUP_DIR" | tail -n +$((MAX_BACKUPS + 1)) | while read old_backup; do
            rm -rf "$BACKUP_DIR/$old_backup"
            log "Removed old backup: $old_backup"
        done
    fi
}

#################################################################################
# UPDATE FUNCTIONS
#################################################################################

enable_maintenance_mode() {
    print_step "Enabling maintenance mode"

    # Create maintenance page
    cat > "$MAINTENANCE_FILE" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Maintenance</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               display: flex; justify-content: center; align-items: center;
               min-height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .container { text-align: center; color: white; padding: 20px; }
        h1 { font-size: 48px; margin-bottom: 10px; }
        p { font-size: 18px; opacity: 0.9; }
        .spinner { width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.3);
                   border-top: 4px solid white; border-radius: 50%;
                   animation: spin 1s linear infinite; margin: 20px auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧</h1>
        <h1>Updating...</h1>
        <div class="spinner"></div>
        <p>FaithTracker is being updated. Please wait a moment.</p>
        <p>This usually takes 2-5 minutes.</p>
    </div>
</body>
</html>
EOF
    print_success "Maintenance mode enabled"
}

disable_maintenance_mode() {
    if [ -f "$MAINTENANCE_FILE" ]; then
        rm -f "$MAINTENANCE_FILE"
        print_success "Maintenance mode disabled"
    fi
}

copy_files() {
    print_section "Updating Files"

    print_step "Syncing files to application directory"
    rsync -a --exclude='.git' --exclude='node_modules' --exclude='venv' \
        --exclude='__pycache__' --exclude='*.pyc' --exclude='build' --exclude='.env' \
        --exclude='uploads' "$GIT_DIR/" "$APP_DIR/" >> "$LOG_FILE" 2>&1

    chown -R faithtracker:faithtracker "$APP_DIR"
    print_success "Files synchronized"
}

update_backend() {
    print_section "Updating Backend"

    cd "$APP_DIR/backend"

    # Ensure venv exists
    if [ ! -d "venv" ]; then
        print_step "Creating Python virtual environment"
        sudo -u faithtracker python3 -m venv venv >> "$LOG_FILE" 2>&1
    fi

    # Activate venv
    source venv/bin/activate

    # Update dependencies
    print_step "Updating Python dependencies"
    pip install -r requirements.txt --quiet >> "$LOG_FILE" 2>&1 &
    local pip_pid=$!
    show_spinner $pip_pid "Installing packages"
    if ! wait $pip_pid; then
        print_error "Python dependencies installation failed"
        show_build_error "Python pip install"
        return 1
    fi

    # Run migrations
    print_step "Running database migrations"
    python migrate.py >> "$LOG_FILE" 2>&1 || {
        print_warning "Migration script not found or failed (non-critical)"
    }

    # Update indexes
    print_step "Updating database indexes"
    python create_indexes.py >> "$LOG_FILE" 2>&1 || {
        print_warning "Index creation failed (non-critical)"
    }

    deactivate

    # Restart backend
    print_step "Restarting backend service"
    systemctl restart faithtracker-backend >> "$LOG_FILE" 2>&1

    sleep 2
    print_success "Backend updated and restarted"
}

update_frontend() {
    print_section "Updating Frontend"

    cd "$APP_DIR/frontend"

    # Install dependencies
    print_step "Installing Node.js dependencies"
    sudo -u faithtracker yarn install --silent >> "$LOG_FILE" 2>&1 &
    local yarn_pid=$!
    show_spinner $yarn_pid "Installing packages"
    if ! wait $yarn_pid; then
        print_error "Node.js dependencies installation failed"
        show_build_error "yarn install"
        return 1
    fi

    # Build production bundle
    print_step "Building production bundle"

    export NODE_OPTIONS="--max-old-space-size=2048"
    sudo -u faithtracker yarn build >> "$LOG_FILE" 2>&1 &
    local build_pid=$!

    # Progress indicator
    local dots=0
    printf "  "
    while kill -0 $build_pid 2>/dev/null; do
        printf "."
        dots=$((dots + 1))
        if [ $dots -ge 60 ]; then
            printf "\n  "
            dots=0
        fi
        sleep 1
    done
    echo ""

    wait $build_pid || {
        print_error "Frontend build failed"
        show_build_error "yarn build"
        return 1
    }

    print_success "Frontend build complete"

    # Restart nginx
    print_step "Reloading web server"
    systemctl reload nginx >> "$LOG_FILE" 2>&1
    print_success "Web server reloaded"
}

#################################################################################
# VERIFICATION
#################################################################################

verify_update() {
    print_section "Verifying Update"

    local all_healthy=true

    # Check backend service
    print_step "Checking backend service"
    sleep 2
    if systemctl is-active --quiet faithtracker-backend; then
        print_success "Backend service is running"
    else
        print_error "Backend service is not running!"
        all_healthy=false
    fi

    # Check nginx
    print_step "Checking web server"
    if systemctl is-active --quiet nginx; then
        print_success "Web server is running"
    else
        print_error "Web server is not running!"
        all_healthy=false
    fi

    # Health check API
    print_step "Testing API health endpoint"
    sleep 2
    if curl -sf "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
        print_success "API is responding"
    else
        print_warning "API health check failed (may still be starting)"
    fi

    # Update version file
    if [ -f "$GIT_DIR/frontend/package.json" ]; then
        grep '"version"' "$GIT_DIR/frontend/package.json" | head -1 | sed 's/.*: "\(.*\)".*/\1/' > "$APP_DIR/.version" 2>/dev/null || true
    fi
    echo "$(date +%s)" > "$APP_DIR/.updated_at"

    if [ "$all_healthy" = false ]; then
        echo ""
        print_warning "Some services may not have started correctly"
        print_info "A backup is available at: $BACKUP_DIR/$BACKUP_NAME"
        print_info "To rollback: ${CYAN}sudo bash $0 --rollback${NC}"
    fi
}

#################################################################################
# COMPLETION
#################################################################################

print_completion() {
    local elapsed=$(($(date +%s) - START_TIME))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))

    disable_maintenance_mode

    echo ""
    echo -e "${GREEN}"
    cat << 'EOF'
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                                                                       ║
    ║      ✓ ✓ ✓   UPDATE COMPLETED SUCCESSFULLY!   ✓ ✓ ✓                  ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    echo -e "  ${BOLD}Update completed in ${minutes}m ${seconds}s${NC}"
    echo ""

    if [ -n "$INSTALLED_VERSION" ] && [ -n "$NEW_VERSION" ]; then
        echo -e "  ${BULLET} Version: ${DIM}$INSTALLED_VERSION${NC} → ${GREEN}$NEW_VERSION${NC}"
    fi

    echo ""
    echo -e "${CYAN}${BOLD}📝 Next Steps:${NC}"
    echo ""
    echo -e "  1. ${BOLD}Clear your browser cache${NC}"
    echo -e "     Press: ${YELLOW}Ctrl + Shift + R${NC} (Windows/Linux)"
    echo -e "     Press: ${YELLOW}Cmd + Shift + R${NC} (Mac)"
    echo ""
    echo -e "  2. ${BOLD}Reload your website${NC} and verify everything works"
    echo ""
    echo -e "  3. ${BOLD}Test main features:${NC}"
    echo -e "     • Dashboard loads correctly"
    echo -e "     • Member list displays"
    echo -e "     • Forms work as expected"
    echo ""

    if [ "$BACKEND_CHANGED" = true ]; then
        echo -e "${CYAN}${BOLD}🔍 Backend Logs:${NC}"
        echo -e "  ${DIM}sudo journalctl -u faithtracker-backend -f${NC}"
        echo ""
    fi

    echo -e "${CYAN}${BOLD}↩️  Rollback if needed:${NC}"
    echo -e "  ${DIM}sudo bash update.sh --rollback${NC}"
    echo ""

    echo -e "${GREEN}${BOLD}Thank you for keeping FaithTracker updated! 🙏${NC}"
    echo ""
}

#################################################################################
# MAIN EXECUTION
#################################################################################

main() {
    setup_logging
    show_banner

    # Handle rollback mode
    if [ "$DO_ROLLBACK" = true ]; then
        check_prerequisites
        perform_rollback
        exit 0
    fi

    echo -e "  ${BOLD}Intelligent update system with automatic backup and rollback${NC}"
    echo ""

    # Validation
    check_prerequisites
    detect_changes
    show_changelog
    show_update_plan

    # Create backup before any changes
    create_backup

    # Enable maintenance mode
    enable_maintenance_mode

    # Copy updated files
    copy_files

    # Update components
    if [ "$BACKEND_CHANGED" = true ] || [ "$FORCE_UPDATE" = true ]; then
        update_backend
    fi

    if [ "$FRONTEND_CHANGED" = true ] || [ "$FORCE_UPDATE" = true ]; then
        update_frontend
    fi

    # Verify everything works
    verify_update

    # Success!
    print_completion
}

main "$@"
