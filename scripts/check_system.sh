#!/bin/bash

# System health and configuration check script
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[INFO] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

info() {
    echo -e "${BLUE}[CHECK] $1${NC}"
}

# Check Docker installation
check_docker() {
    info "Checking Docker installation..."
    
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        log "Docker installed: $DOCKER_VERSION"
    else
        error "Docker is not installed"
        return 1
    fi
    
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version)
        log "Docker Compose installed: $COMPOSE_VERSION"
    else
        error "Docker Compose is not installed"
        return 1
    fi
}

# Check environment files
check_env_files() {
    info "Checking environment files..."
    
    if [ -f .env ]; then
        log ".env file exists"
        
        # Check for required variables
        required_vars=("BRAVE_SEARCH_API_KEY" "SERPAPI_API_KEY" "ZENROWS_API_KEY" "SECRET_KEY")
        for var in "${required_vars[@]}"; do
            if grep -q "^$var=" .env; then
                value=$(grep "^$var=" .env | cut -d '=' -f2)
                if [ -n "$value" ] && [ "$value" != "your_api_key_here" ] && [ "$value" != "change_this" ]; then
                    log "$var is configured"
                else
                    warn "$var needs to be set"
                fi
            else
                warn "$var is missing from .env"
            fi
        done
    else
        error ".env file is missing"
    fi
    
    if [ -f .env.prod ]; then
        log ".env.prod file exists"
    else
        warn ".env.prod file is missing (needed for production)"
    fi
}

# Check Docker services
check_services() {
    info "Checking Docker services..."
    
    if docker-compose ps | grep -q "Up"; then
        log "Some services are running"
        docker-compose ps
    else
        warn "No services are currently running"
    fi
}

# Check system resources
check_resources() {
    info "Checking system resources..."
    
    # Check disk space
    DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -gt 80 ]; then
        warn "Disk usage is high: $DISK_USAGE%"
    else
        log "Disk usage: $DISK_USAGE%"
    fi
    
    # Check memory
    if command -v free &> /dev/null; then
        MEMORY_INFO=$(free -h | grep "Mem:")
        log "Memory: $MEMORY_INFO"
    fi
    
    # Check Docker storage
    DOCKER_USAGE=$(docker system df 2>/dev/null | tail -n +2 | awk '{print $3}' | head -1 || echo "N/A")
    log "Docker storage usage: $DOCKER_USAGE"
}

# Check network connectivity
check_network() {
    info "Checking network connectivity..."
    
    # Test external API endpoints
    apis=(
        "https://api.search.brave.com"
        "https://serpapi.com"
        "https://api.zenrows.com"
    )
    
    for api in "${apis[@]}"; do
        if curl -s --max-time 5 "$api" > /dev/null; then
            log "$api is reachable"
        else
            warn "$api is not reachable"
        fi
    done
}

# Check application health
check_app_health() {
    info "Checking application health..."
    
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log "API is responding"
        
        # Get detailed health info
        HEALTH_INFO=$(curl -s http://localhost:8000/health/detailed 2>/dev/null || echo "Detailed health unavailable")
        echo "$HEALTH_INFO" | jq . 2>/dev/null || echo "$HEALTH_INFO"
    else
        warn "API is not responding on localhost:8000"
    fi
}

# Main check function
main() {
    echo "🔍 LLM Search Backend System Check"
    echo "=================================="
    echo ""
    
    check_docker
    echo ""
    
    check_env_files
    echo ""
    
    check_services
    echo ""
    
    check_resources
    echo ""
    
    check_network
    echo ""
    
    check_app_health
    echo ""
    
    log "System check completed!"
}

main "$@"
