#!/bin/bash
# docker/production-startup.sh - Production startup script for Railway/Docker

set -e

echo "🚀 Starting LLM Search Backend (Production Mode)"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if a service is ready
wait_for_service() {
    local service=$1
    local url=$2
    local max_attempts=${3:-60}
    local attempt=1
    
    log "⏳ Waiting for $service to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" >/dev/null 2>&1; then
            log "✅ $service is ready!"
            return 0
        fi
        
        if [ $((attempt % 15)) -eq 0 ]; then
            log "🔄 Still waiting for $service... ($attempt/$max_attempts)"
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log "❌ $service failed to become ready after $max_attempts attempts"
    return 1
}

# Function to start Ollama service
start_ollama() {
    log "🤖 Starting Ollama service..."
    
    # Start Ollama in background as ollama user
    su ollama -c "OLLAMA_HOST=0.0.0.0:11434 OLLAMA_MODELS=/home/ollama/.ollama/models ollama serve" &
    OLLAMA_PID=$!
    
    # Wait for Ollama to be ready
    if wait_for_service "Ollama" "http://localhost:11434/api/version" 30; then
        log "📥 Checking for llama2:7b model..."
        
        # Check if model already exists
        if su ollama -c "ollama list | grep llama2:7b" >/dev/null 2>&1; then
            log "✅ Model llama2:7b already available!"
            return 0
        fi
        
        log "📥 Pulling llama2:7b model (first time setup, ~5-10 minutes)..."
        
        # Pull the model with timeout and retry
        local model_pull_attempts=2
        local attempt=1
        
        while [ $attempt -le $model_pull_attempts ]; do
            log "🔄 Model pull attempt $attempt/$model_pull_attempts..."
            
            # Use timeout to prevent hanging
            if timeout 900 su ollama -c "ollama pull llama2:7b" 2>&1; then
                log "✅ Model llama2:7b pulled successfully!"
                return 0
            else
                log "⚠️ Model pull attempt $attempt failed or timed out"
                if [ $attempt -lt $model_pull_attempts ]; then
                    log "🔄 Retrying model pull in 30 seconds..."
                    sleep 30
                fi
                attempt=$((attempt + 1))
            fi
        done
        
        log "⚠️ Model pull failed, but continuing startup"
        log "ℹ️ Model can be pulled automatically on first LLM request"
        return 0
    else
        log "❌ Ollama failed to start properly"
        return 1
    fi
}

# Function to run database migrations
run_migrations() {
    log "🔄 Running database migrations..."
    
    if [ -f "scripts/manage_migrations.py" ]; then
        if python scripts/manage_migrations.py upgrade 2>&1; then
            log "✅ Database migrations completed"
        else
            log "⚠️ Database migration issues (may be normal for first deploy)"
        fi
    else
        log "ℹ️ No migration script found, skipping"
    fi
}

# Function to start the FastAPI application
start_app() {
    log "🌐 Starting FastAPI application (Production Mode)..."
    
    # Switch to appuser and start the application with production settings
    exec su appuser -c "uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --access-log \
        --log-level info \
        --loop asyncio"
}

# Function to handle cleanup
cleanup() {
    log "🧹 Shutting down services..."
    
    # Kill Ollama process if it exists
    if [ ! -z "$OLLAMA_PID" ] && kill -0 $OLLAMA_PID 2>/dev/null; then
        log "🛑 Stopping Ollama service..."
        kill -TERM $OLLAMA_PID 2>/dev/null || true
        
        # Wait for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 $OLLAMA_PID 2>/dev/null; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        kill -KILL $OLLAMA_PID 2>/dev/null || true
    fi
    
    log "✅ Cleanup completed"
    exit 0
}

# Set up signal handlers for graceful shutdown
trap cleanup SIGTERM SIGINT SIGQUIT

# Function to verify system requirements
check_system() {
    log "🔍 Checking system requirements..."
    
    # Check available memory (fixed version)
    local mem_available
    if command -v free >/dev/null 2>&1; then
        mem_available=$(free -m 2>/dev/null | awk 'NR==2{printf "%.0f", $7}' || echo "0")
        if [ "$mem_available" -gt 0 ] && [ "$mem_available" -lt 2048 ]; then
            log "⚠️ Warning: Low available memory (${mem_available}MB). Ollama may struggle."
            log "💡 Recommendation: Increase container memory to 4GB+"
        elif [ "$mem_available" -gt 0 ]; then
            log "✅ Memory check passed (${mem_available}MB available)"
        else
            log "ℹ️ Memory check skipped (unable to determine available memory)"
        fi
    else
        log "ℹ️ Memory check skipped (free command not available)"
    fi
    
    # Check disk space
    local disk_available
    if command -v df >/dev/null 2>&1; then
        disk_available=$(df /home/ollama/.ollama 2>/dev/null | awk 'NR==2 {print $4}' || echo "unknown")
        if [ "$disk_available" != "unknown" ] && [ "$disk_available" -lt 5000000 ]; then
            log "⚠️ Warning: Low disk space. Model downloads may fail."
        fi
    fi
}

# Main execution function
main() {
    log "🎬 Starting production deployment sequence..."
    
    # System checks
    check_system
    
    # Start Ollama service (in background)
    if start_ollama; then
        log "✅ Ollama service setup completed"
    else
        log "⚠️ Ollama setup had issues, but continuing with app startup"
        log "ℹ️ LLM features will use fallback responses until Ollama is ready"
    fi
    
    # Run database migrations
    run_migrations
    
    # Start the main FastAPI application (this becomes the main process)
    log "🚀 Starting main application..."
    start_app
}

# Execute main function
main "$@"
