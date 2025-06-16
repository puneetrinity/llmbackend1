#!/bin/bash
# docker/nginx-start.sh
set -e

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] NGINX-START: $1"
}

log "NGINX startup script initiated..."

# Wait for API service to be ready
wait_for_api() {
    local host=${API_HOST:-api}
    local port=${API_PORT:-8000}
    local max_attempts=30
    local attempt=1
    
    log "Waiting for API service at $host:$port to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z $host $port 2>/dev/null; then
            log "API service is ready!"
            return 0
        fi
        
        log "Attempt $attempt/$max_attempts: API service not ready, waiting 2 seconds..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log "WARNING: API service not responding after $max_attempts attempts, proceeding anyway"
    return 1
}

# Check if netcat is available, install if needed
if ! command -v nc >/dev/null 2>&1; then
    log "Installing netcat for health checks..."
    apk add --no-cache netcat-openbsd
fi

# Wait for API service (non-blocking)
wait_for_api || true

# Final nginx configuration test
log "Performing final NGINX configuration test..."
if nginx -t; then
    log "NGINX configuration is valid and ready"
else
    log "ERROR: NGINX configuration test failed"
    exit 1
fi

# Create PID directory
mkdir -p /var/run

# Set proper permissions
chown nginx:nginx /var/run/nginx.pid 2>/dev/null || true

log "NGINX startup script completed successfully"
exit 0
