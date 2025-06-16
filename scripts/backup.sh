#!/bin/bash

set -e

# Configuration
BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_CONTAINER="db"
COMPOSE_FILE="docker-compose.yml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Create backup directory
create_backup_dir() {
    mkdir -p $BACKUP_DIR
    log "Created backup directory: $BACKUP_DIR"
}

# Backup database
backup_database() {
    log "Starting database backup..."
    
    BACKUP_FILE="$BACKUP_DIR/database_backup_$DATE.sql"
    
    if docker-compose -f $COMPOSE_FILE exec -T $DB_CONTAINER pg_dump -U searchuser -d searchdb > $BACKUP_FILE; then
        log "Database backup completed: $BACKUP_FILE"
        
        # Compress backup
        gzip $BACKUP_FILE
        log "Backup compressed: $BACKUP_FILE.gz"
    else
        error "Database backup failed"
        exit 1
    fi
}

# Backup Redis data
backup_redis() {
    log "Starting Redis backup..."
    
    REDIS_BACKUP_DIR="$BACKUP_DIR/redis_$DATE"
    mkdir -p $REDIS_BACKUP_DIR
    
    if docker-compose -f $COMPOSE_FILE exec -T redis redis-cli SAVE; then
        docker cp $(docker-compose -f $COMPOSE_FILE ps -q redis):/data/dump.rdb $REDIS_BACKUP_DIR/
        log "Redis backup completed: $REDIS_BACKUP_DIR"
    else
        warn "Redis backup failed"
    fi
}

# Backup application data
backup_app_data() {
    log "Starting application data backup..."
    
    APP_BACKUP_DIR="$BACKUP_DIR/app_data_$DATE"
    mkdir -p $APP_BACKUP_DIR
    
    # Backup logs
    if [ -d "logs" ]; then
        cp -r logs $APP_BACKUP_DIR/
        log "Logs backed up"
    fi
    
    # Backup configuration files
    cp .env* $APP_BACKUP_DIR/ 2>/dev/null || true
    cp docker-compose*.yml $APP_BACKUP_DIR/
    
    log "Application data backup completed: $APP_BACKUP_DIR"
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups..."
    
    # Keep only last 7 days of backups
    find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
    find $BACKUP_DIR -name "redis_*" -mtime +7 -exec rm -rf {} \;
    find $BACKUP_DIR -name "app_data_*" -mtime +7 -exec rm -rf {} \;
    
    log "Old backups cleaned up"
}

# Create backup archive
create_archive() {
    log "Creating backup archive..."
    
    ARCHIVE_NAME="full_backup_$DATE.tar.gz"
    tar -czf $BACKUP_DIR/$ARCHIVE_NAME -C $BACKUP_DIR database_backup_$DATE.sql.gz redis_$DATE app_data_$DATE
    
    log "Backup archive created: $BACKUP_DIR/$ARCHIVE_NAME"
}

# Main backup function
main() {
    log "Starting backup process..."
    
    create_backup_dir
    backup_database
    backup_redis
    backup_app_data
    create_archive
    cleanup_old_backups
    
    log "Backup process completed successfully!"
    log "Backup location: $BACKUP_DIR"
}

main "$@"
