#!/bin/bash

# Health check script for Docker containers
set -e

# Configuration
API_URL="http://localhost:8000"
TIMEOUT=10

# Function to check API health
check_api() {
    curl -f -s -m $TIMEOUT "$API_URL/health" > /dev/null
    return $?
}

# Function to check database health
check_database() {
    curl -f -s -m $TIMEOUT "$API_URL/health/database" > /dev/null
    return $?
}

# Main health check
main() {
    # Check API first
    if check_api; then
        echo "API health check passed"
    else
        echo "API health check failed"
        exit 1
    fi
    
    # Check database
    if check_database; then
        echo "Database health check passed"
    else
        echo "Database health check failed"
        exit 1
    fi
    
    echo "All health checks passed"
    exit 0
}

main "$@"
