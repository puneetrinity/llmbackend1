#!/bin/bash
set -e

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting NGINX configuration setup..."

# Default values
API_HOST=${API_HOST:-api}
API_PORT=${API_PORT:-8000}
NGINX_PORT=${NGINX_PORT:-80}

# Generate nginx.conf from template if template exists
if [ -f /etc/nginx/nginx.conf.template ]; then
    log "Generating nginx.conf from template..."
    envsubst '${API_HOST} ${API_PORT} ${NGINX_PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
fi

# Test nginx configuration
log "Testing NGINX configuration..."
nginx -t

if [ $? -eq 0 ]; then
    log "NGINX configuration is valid"
else
    log "NGINX configuration is invalid"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p /var/log/nginx

# Start nginx
log "Starting NGINX..."
exec nginx -g 'daemon off;'
