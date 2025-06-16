#!/bin/bash

set -e

# Configuration
BACKUP_FILE=$1
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

# Usage function
usage() {
    echo "Usage: $0 <backup-file>"
    echo "Example: $0 backups/database_backup_20240101_120000.sql.gz"
    exit 1
}

# Validate backup file
validate_backup() {
    if [ -z "$BACKUP_FILE" ]; then
        error "Backup file not specified"
        usage
    fi
    
    if [ ! -f "$BACKUP_FILE" ]; then
        error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
    
    log "Using backup file: $BACKUP_FILE"
}

# Stop application services
stop_services() {
    log "Stopping application services..."
    docker-compose -f $COMPOSE_FILE stop api
}

# Restore database
restore_database() {
    log "Starting database restore..."
    
    # Determine if file is compressed
    if [[ $BACKUP_FILE == *.gz ]]; then
        log "Decompressing backup file..."
        gunzip -c $BACKUP_FILE | docker-compose -f $COMPOSE_FILE exec -T db psql -U searchuser -d searchdb
    else
        docker-compose -f $COMPOSE_FILE exec -T db psql -U searchuser -d searchdb < $BACKUP_FILE
    fi
    
    log "Database restore completed"
}

# Restart services
restart_services() {
    log "Restarting services..."
    docker-compose -f $COMPOSE_FILE up -d
    
    # Wait for services to be ready
    sleep 30
    
    log "Services restarted"
}

# Verify restore
verify_restore() {
    log "Verifying restore..."
    
    # Test database connection
    if docker-compose -f $COMPOSE_FILE exec -T db psql -U searchuser -d searchdb -c "SELECT 1;" > /dev/null; then
        log "✅ Database connection successful"
    else
        error "❌ Database connection failed"
        exit 1
    fi
    
    # Test API health
    sleep 10
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log "✅ API health check passed"
    else
        warn "⚠️  API health check failed - service may still be starting"
    fi
}

# Main restore function
main() {
    log "Starting restore process..."
    
    validate_backup
    
    # Confirmation prompt
    read -p "This will restore the database and restart services. Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Restore cancelled"
        exit 0
    fi
    
    stop_services
    restore_database
    restart_services
    verify_restore
    
    log "Restore process completed successfully!"
}

main "$@"
