#!/bin/bash
# ===========================================
# FaithTracker Backup Script
# ===========================================
# Creates timestamped backups of MongoDB database and uploads
# Stores backups in ./backups/ directory
# Automatically cleans up backups older than 30 days
#
# Usage:
#   ./scripts/backup-db.sh              # Backup database only
#   ./scripts/backup-db.sh --full       # Backup database + uploads (recommended)
#   ./scripts/backup-db.sh --restore    # Restore latest database backup
#   ./scripts/backup-db.sh --restore-full  # Restore database + uploads
#
# Cron example (daily at 2 AM):
#   0 2 * * * /path/to/faithtracker/scripts/backup-db.sh --full >> /var/log/faithtracker-backup.log 2>&1

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
DATA_DIR="${PROJECT_DIR}/data"
UPLOADS_DIR="${DATA_DIR}/uploads"
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

backup_uploads() {
    log_info "Starting uploads backup..."

    if [ ! -d "${UPLOADS_DIR}" ]; then
        log_warn "Uploads directory not found: ${UPLOADS_DIR}"
        return 0
    fi

    UPLOADS_BACKUP="${BACKUP_DIR}/faithtracker_uploads_${TIMESTAMP}.tar.gz"

    # Count files
    FILE_COUNT=$(find "${UPLOADS_DIR}" -type f | wc -l)
    log_info "Found ${FILE_COUNT} files to backup"

    if [ "$FILE_COUNT" -eq 0 ]; then
        log_info "No files to backup in uploads"
        return 0
    fi

    tar -czf "${UPLOADS_BACKUP}" -C "${DATA_DIR}" uploads

    if [ -f "${UPLOADS_BACKUP}" ]; then
        BACKUP_SIZE=$(du -h "${UPLOADS_BACKUP}" | cut -f1)
        log_info "Uploads backup created: ${UPLOADS_BACKUP} (${BACKUP_SIZE})"
    else
        log_error "Uploads backup failed"
        exit 1
    fi
}

restore_uploads() {
    local BACKUP_FILE="$1"

    if [ -z "${BACKUP_FILE}" ]; then
        # Use latest backup
        BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/faithtracker_uploads_*.tar.gz 2>/dev/null | head -1)
        if [ -z "${BACKUP_FILE}" ]; then
            log_error "No uploads backup files found in ${BACKUP_DIR}"
            exit 1
        fi
    fi

    if [ ! -f "${BACKUP_FILE}" ]; then
        log_error "Uploads backup file not found: ${BACKUP_FILE}"
        exit 1
    fi

    log_warn "This will OVERWRITE the current uploads!"
    log_warn "Backup file: ${BACKUP_FILE}"
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        log_info "Restore cancelled"
        exit 0
    fi

    log_info "Starting uploads restore..."

    # Create backup of current uploads before restoring
    if [ -d "${UPLOADS_DIR}" ] && [ "$(ls -A "${UPLOADS_DIR}")" ]; then
        log_info "Creating backup of current uploads..."
        mv "${UPLOADS_DIR}" "${UPLOADS_DIR}.bak.${TIMESTAMP}"
    fi

    mkdir -p "${DATA_DIR}"
    tar -xzf "${BACKUP_FILE}" -C "${DATA_DIR}"

    log_info "Uploads restore completed successfully"

    # Clean up old backup if restore was successful
    if [ -d "${UPLOADS_DIR}.bak.${TIMESTAMP}" ]; then
        rm -rf "${UPLOADS_DIR}.bak.${TIMESTAMP}"
        log_info "Cleaned up temporary backup"
    fi
}

full_backup() {
    log_info "=== Starting full backup (database + uploads) ==="
    backup_database
    backup_uploads
    cleanup_old_backups
    log_info "=== Full backup completed ==="
}

full_restore() {
    log_info "=== Starting full restore (database + uploads) ==="
    restore_database "$1"
    restore_uploads "$2"
    log_info "=== Full restore completed ==="
}

cleanup_old_backups() {
    log_info "Cleaning up backups older than ${RETENTION_DAYS} days..."

    # Clean old database backups
    DB_DELETED=$(find "${BACKUP_DIR}" -name "faithtracker_*.archive" -mtime +${RETENTION_DAYS} -delete -print 2>/dev/null | wc -l)

    # Clean old uploads backups
    UPLOADS_DELETED=$(find "${BACKUP_DIR}" -name "faithtracker_uploads_*.tar.gz" -mtime +${RETENTION_DAYS} -delete -print 2>/dev/null | wc -l)

    TOTAL_DELETED=$((DB_DELETED + UPLOADS_DELETED))

    if [ "$TOTAL_DELETED" -gt 0 ]; then
        log_info "Deleted ${TOTAL_DELETED} old backup(s) (${DB_DELETED} db, ${UPLOADS_DELETED} uploads)"
    else
        log_info "No old backups to delete"
    fi
}

list_backups() {
    log_info "Available backups in ${BACKUP_DIR}:"
    echo ""
    echo "Database backups:"
    ls -lh "${BACKUP_DIR}"/faithtracker_*.archive 2>/dev/null || echo "  No database backups found"
    echo ""
    echo "Uploads backups:"
    ls -lh "${BACKUP_DIR}"/faithtracker_uploads_*.tar.gz 2>/dev/null || echo "  No uploads backups found"
    echo ""
}

# Main script logic
case "${1}" in
    --full)
        full_backup
        ;;
    --restore)
        restore_database "$2"
        ;;
    --restore-uploads)
        restore_uploads "$2"
        ;;
    --restore-full)
        restore_database "$2"
        restore_uploads "$3"
        ;;
    --uploads)
        backup_uploads
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
        echo "  (no option)       Backup database only"
        echo "  --full            Backup database + uploads (recommended)"
        echo "  --uploads         Backup uploads only"
        echo "  --restore         Restore latest database backup"
        echo "  --restore FILE    Restore specific database backup"
        echo "  --restore-uploads Restore latest uploads backup"
        echo "  --restore-full    Restore both database and uploads"
        echo "  --list            List available backups"
        echo "  --cleanup         Remove backups older than ${RETENTION_DAYS} days"
        echo "  --help            Show this help message"
        echo ""
        echo "Data location: ${DATA_DIR}"
        echo "  - MongoDB:  ${DATA_DIR}/mongo"
        echo "  - Uploads:  ${DATA_DIR}/uploads"
        ;;
    *)
        backup_database
        cleanup_old_backups
        ;;
esac
