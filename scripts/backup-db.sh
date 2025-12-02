#!/bin/bash
# ===========================================
# FaithTracker Database Backup Script
# ===========================================
# Creates a timestamped backup of the MongoDB database
# Stores backups in ./backups/ directory
# Automatically cleans up backups older than 30 days
#
# Usage:
#   ./scripts/backup-db.sh              # Create backup
#   ./scripts/backup-db.sh --restore    # Restore latest backup
#   ./scripts/backup-db.sh --restore <filename>  # Restore specific backup
#
# Cron example (daily at 2 AM):
#   0 2 * * * /path/to/faithtracker/scripts/backup-db.sh >> /var/log/faithtracker-backup.log 2>&1

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Load environment variables
if [ -f "${PROJECT_DIR}/.env" ]; then
    source "${PROJECT_DIR}/.env"
fi

# MongoDB connection details
MONGO_HOST="${MONGO_HOST:-mongo}"
MONGO_USER="${MONGO_ROOT_USERNAME:-admin}"
MONGO_PASS="${MONGO_ROOT_PASSWORD}"
MONGO_DB="${DB_NAME:-faithtracker}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Create backup directory if not exists
mkdir -p "${BACKUP_DIR}"

backup_database() {
    log_info "Starting MongoDB backup..."

    BACKUP_FILE="${BACKUP_DIR}/faithtracker_${TIMESTAMP}.archive"

    # Check if running in Docker
    if docker ps --format '{{.Names}}' | grep -q "faithtracker-mongo"; then
        log_info "Using Docker container for backup..."
        docker exec faithtracker-mongo mongodump \
            --username="${MONGO_USER}" \
            --password="${MONGO_PASS}" \
            --authenticationDatabase=admin \
            --db="${MONGO_DB}" \
            --archive \
            --gzip > "${BACKUP_FILE}"
    else
        log_info "Using mongodump directly..."
        mongodump \
            --host="${MONGO_HOST}" \
            --username="${MONGO_USER}" \
            --password="${MONGO_PASS}" \
            --authenticationDatabase=admin \
            --db="${MONGO_DB}" \
            --archive="${BACKUP_FILE}" \
            --gzip
    fi

    if [ -f "${BACKUP_FILE}" ]; then
        BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
        log_info "Backup created successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"
    else
        log_error "Backup failed - file not created"
        exit 1
    fi
}

restore_database() {
    local BACKUP_FILE="$1"

    if [ -z "${BACKUP_FILE}" ]; then
        # Use latest backup
        BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/faithtracker_*.archive 2>/dev/null | head -1)
        if [ -z "${BACKUP_FILE}" ]; then
            log_error "No backup files found in ${BACKUP_DIR}"
            exit 1
        fi
    fi

    if [ ! -f "${BACKUP_FILE}" ]; then
        log_error "Backup file not found: ${BACKUP_FILE}"
        exit 1
    fi

    log_warn "This will OVERWRITE the current database!"
    log_warn "Backup file: ${BACKUP_FILE}"
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        log_info "Restore cancelled"
        exit 0
    fi

    log_info "Starting database restore..."

    # Check if running in Docker
    if docker ps --format '{{.Names}}' | grep -q "faithtracker-mongo"; then
        log_info "Using Docker container for restore..."
        cat "${BACKUP_FILE}" | docker exec -i faithtracker-mongo mongorestore \
            --username="${MONGO_USER}" \
            --password="${MONGO_PASS}" \
            --authenticationDatabase=admin \
            --db="${MONGO_DB}" \
            --archive \
            --gzip \
            --drop
    else
        log_info "Using mongorestore directly..."
        mongorestore \
            --host="${MONGO_HOST}" \
            --username="${MONGO_USER}" \
            --password="${MONGO_PASS}" \
            --authenticationDatabase=admin \
            --db="${MONGO_DB}" \
            --archive="${BACKUP_FILE}" \
            --gzip \
            --drop
    fi

    log_info "Database restore completed successfully"
}

cleanup_old_backups() {
    log_info "Cleaning up backups older than ${RETENTION_DAYS} days..."

    DELETED_COUNT=$(find "${BACKUP_DIR}" -name "faithtracker_*.archive" -mtime +${RETENTION_DAYS} -delete -print | wc -l)

    if [ "$DELETED_COUNT" -gt 0 ]; then
        log_info "Deleted ${DELETED_COUNT} old backup(s)"
    else
        log_info "No old backups to delete"
    fi
}

list_backups() {
    log_info "Available backups in ${BACKUP_DIR}:"
    echo ""
    ls -lh "${BACKUP_DIR}"/faithtracker_*.archive 2>/dev/null || echo "No backups found"
    echo ""
}

# Main script logic
case "${1}" in
    --restore)
        restore_database "$2"
        ;;
    --list)
        list_backups
        ;;
    --cleanup)
        cleanup_old_backups
        ;;
    --help)
        echo "Usage: $0 [option]"
        echo ""
        echo "Options:"
        echo "  (no option)     Create a new backup"
        echo "  --restore       Restore from latest backup"
        echo "  --restore FILE  Restore from specific backup file"
        echo "  --list          List available backups"
        echo "  --cleanup       Remove backups older than ${RETENTION_DAYS} days"
        echo "  --help          Show this help message"
        ;;
    *)
        backup_database
        cleanup_old_backups
        ;;
esac
